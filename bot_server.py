# Necesitas instalar:
# pip install pyTelegramBotAPI flask flask-socketio requests
import os
import sqlite3
import telebot
import requests
import json
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
from telebot import types
import threading

# ============= CONFIGURACIÓN =============
# Obtener configuración desde variables de entorno (para Railway)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8432915259:AAEOFgo5nvNhmiJEz6GNd-U3QQIY5xvRP_8')
FLASK_PORT = int(os.environ.get('PORT', 5000))  # Railway usa la variable PORT
MERCADOPAGO_ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN', 'TU_ACCESS_TOKEN_AQUI')
RAILWAY_PUBLIC_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
NGROK_URL = os.environ.get('NGROK_URL', 'https://unprisonable-armanda-chanceless.ngrok-free.dev')

# Usar Railway URL si está disponible, sino usar ngrok
PUBLIC_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}" if RAILWAY_PUBLIC_DOMAIN else NGROK_URL

# ============= BASE DE DATOS =============

def init_db():
    conn = sqlite3.connect('bot_messages.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS conversaciones
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER UNIQUE,
                  username TEXT,
                  nombre TEXT,
                  estado TEXT DEFAULT 'nuevo',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS mensajes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  conversacion_id INTEGER,
                  user_id INTEGER,
                  mensaje TEXT,
                  tipo TEXT DEFAULT 'usuario',
                  media_type TEXT,
                  media_path TEXT,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (conversacion_id) REFERENCES conversaciones(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS pagos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  payment_id TEXT,
                  preference_id TEXT,
                  monto REAL,
                  estado TEXT DEFAULT 'pending',
                  concepto TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

def guardar_mensaje(user_id, username, nombre, mensaje, tipo='usuario', media_type=None, media_path=None):
    conn = sqlite3.connect('bot_messages.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute('SELECT id FROM conversaciones WHERE user_id = ?', (user_id,))
    resultado = c.fetchone()
    
    if resultado:
        conv_id = resultado[0]
        c.execute('''UPDATE conversaciones 
                     SET updated_at = CURRENT_TIMESTAMP,
                         nombre = ?, username = ?
                     WHERE id = ?''', (nombre, username, conv_id))
    else:
        c.execute('''INSERT INTO conversaciones (user_id, username, nombre, estado)
                     VALUES (?, ?, ?, 'nuevo')''', (user_id, username, nombre))
        conv_id = c.lastrowid
    
    c.execute('''INSERT INTO mensajes (conversacion_id, user_id, mensaje, tipo, media_type, media_path)
                 VALUES (?, ?, ?, ?, ?, ?)''', (conv_id, user_id, mensaje, tipo, media_type, media_path))
    
    conn.commit()
    conn.close()
    
    # Notificar al panel web
    socketio.emit('nuevo_mensaje', {
        'user_id': user_id,
        'nombre': nombre,
        'mensaje': mensaje,
        'tipo': tipo,
        'media_type': media_type,
        'media_path': media_path
    })
    
    return conv_id

# ============= MERCADOPAGO =============

def crear_link_pago(user_id, monto, concepto="Solicitud de CBU"):
    """Crea un link de pago de MercadoPago"""
    
    url = "https://api.mercadopago.com/checkout/preferences"
    
    headers = {
        "Authorization": f"Bearer {MERCADOPAGO_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Datos del pago
    preference_data = {
        "items": [
            {
                "title": concepto,
                "quantity": 1,
                "unit_price": float(monto),
                "currency_id": "ARS"
            }
        ],
        "back_urls": {
            "success": f"{PUBLIC_URL}/pago/success",
            "failure": f"{PUBLIC_URL}/pago/failure",
            "pending": f"{PUBLIC_URL}/pago/pending"
        },
        "auto_return": "approved",
        "external_reference": str(user_id),
        "notification_url": f"{PUBLIC_URL}/webhook/mercadopago"
    }
    
    try:
        response = requests.post(url, json=preference_data, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        init_point = data.get('init_point')
        preference_id = data.get('id')
        
        # Guardar pago en BD
        conn = sqlite3.connect('bot_messages.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''INSERT INTO pagos (user_id, preference_id, monto, concepto, estado)
                     VALUES (?, ?, ?, ?, 'pending')''', (user_id, preference_id, monto, concepto))
        conn.commit()
        conn.close()
        
        print(f"💳 Link de pago creado: {init_point}")
        return init_point, preference_id
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al crear link de pago: {e}")
        return None, None

# ============= BOT DE TELEGRAM =============

bot = telebot.TeleBot(BOT_TOKEN)

def crear_menu_principal():
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("💳 Pasar CBU", callback_data='cbu'))
    markup.row(types.InlineKeyboardButton("💬 Hablar con soporte", callback_data='soporte'))
    markup.row(types.InlineKeyboardButton("💸 Retirar dinero", callback_data='retiro'))
    markup.row(types.InlineKeyboardButton("❓ Preguntas frecuentes", callback_data='faq'))
    return markup

def crear_menu_navegacion():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("💳 CBU", callback_data='cbu'),
        types.InlineKeyboardButton("💬 Soporte", callback_data='soporte')
    )
    markup.row(
        types.InlineKeyboardButton("💸 Retiro", callback_data='retiro'),
        types.InlineKeyboardButton("🏠 Inicio", callback_data='inicio')
    )
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user
    nombre = user.first_name or "Usuario"
    
    bot.reply_to(
        message,
        f"¡Hola *{nombre}*! 👋\n\n"
        f"Bienvenido/a. Selecciona la opción que necesites:",
        reply_markup=crear_menu_principal(),
        parse_mode='Markdown'
    )
    
    guardar_mensaje(user.id, user.username, nombre, "/start", "sistema")
    print(f"✅ Usuario {nombre} ({user.id}) inició el bot")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def recibir_mensaje(message):
    user = message.from_user
    nombre = user.first_name or "Usuario"
    mensaje = message.text
    
    guardar_mensaje(user.id, user.username, nombre, mensaje, "usuario")
    print(f"📩 Mensaje de {nombre}: {mensaje}")
    
    bot.reply_to(
        message,
        f"✅ Mensaje recibido, *{nombre}*\n\n"
        f"Te responderemos pronto.",
        reply_markup=crear_menu_navegacion(),
        parse_mode='Markdown'
    )

@bot.message_handler(content_types=['photo'])
def recibir_imagen(message):
    user = message.from_user
    nombre = user.first_name or "Usuario"
    
    # Obtener la imagen de mayor calidad
    photo = message.photo[-1]
    file_info = bot.get_file(photo.file_id)
    
    # Descargar la imagen
    downloaded_file = bot.download_file(file_info.file_path)
    
    # Crear carpeta para imágenes si no existe
    if not os.path.exists('media/images'):
        os.makedirs('media/images')
    
    # Guardar imagen con nombre único
    image_filename = f"{user.id}_{int(datetime.now().timestamp())}_{photo.file_id[:10]}.jpg"
    image_path = f"media/images/{image_filename}"
    
    with open(image_path, 'wb') as new_file:
        new_file.write(downloaded_file)
    
    # Guardar información de la imagen
    caption = message.caption or ""
    mensaje_texto = f"📷 Imagen{': ' + caption if caption else ''}"
    
    guardar_mensaje(user.id, user.username, nombre, mensaje_texto, "usuario", "image", image_path)
    print(f"📷 Imagen guardada de {nombre}: {image_path}")
    
    bot.reply_to(
        message,
        f"✅ Imagen recibida, *{nombre}*\n\n"
        f"Te responderemos pronto.",
        reply_markup=crear_menu_navegacion(),
        parse_mode='Markdown'
    )

@bot.message_handler(content_types=['document', 'video', 'audio', 'voice', 'sticker'])
def recibir_archivo(message):
    user = message.from_user
    nombre = user.first_name or "Usuario"
    
    tipo_archivo = message.content_type
    caption = message.caption or ""
    mensaje_texto = f"📎 [{tipo_archivo.upper()} recibido] {caption}" if caption else f"📎 [{tipo_archivo.upper()} recibido]"
    
    guardar_mensaje(user.id, user.username, nombre, mensaje_texto, "usuario")
    print(f"📎 {tipo_archivo} recibido de {nombre}")
    
    bot.reply_to(
        message,
        f"✅ Archivo recibido, *{nombre}*\n\n"
        f"Te responderemos pronto.",
        reply_markup=crear_menu_navegacion(),
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: True)
def manejar_botones(call):
    user = call.from_user
    nombre = user.first_name or "Usuario"
    data = call.data
    
    bot.answer_callback_query(call.id)
    
    if data == "inicio":
        guardar_mensaje(user.id, user.username, nombre, "🏠 Volvió al menú principal", "sistema")
        bot.edit_message_text(
            f"🏠 *MENÚ PRINCIPAL*\n\nSelecciona una opción:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=crear_menu_principal(),
            parse_mode='Markdown'
        )
    
    elif data == "cbu":
        guardar_mensaje(user.id, user.username, nombre, "💳 Solicitó datos de CBU", "sistema")
        
        # Generar link de pago
        link_pago, preference_id = crear_link_pago(user.id, 1000, "Solicitud de CBU")
        
        if link_pago:
            # Crear botón con el link de pago
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("💰 Pagar $1000", url=link_pago))
            markup.row(types.InlineKeyboardButton("🏠 Volver al inicio", callback_data='inicio'))
            
            bot.edit_message_text(
                f"💳 *SOLICITUD DE CBU*\n\n"
                f"Para acceder a los datos de transferencia, primero debes realizar un pago de *$1,000 ARS*\n\n"
                f"Haz clic en el botón de abajo para pagar con MercadoPago:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
            
            # Guardar el link de pago en los mensajes
            guardar_mensaje(user.id, user.username, nombre, f"💰 Link de pago generado: $1000", "sistema")
        else:
            bot.edit_message_text(
                "❌ *ERROR*\n\nNo se pudo generar el link de pago. Por favor, contacta al administrador.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=crear_menu_navegacion(),
                parse_mode='Markdown'
            )
        
        print(f"💳 {nombre} solicitó CBU - Link de pago enviado")
    
    elif data == "soporte":
        guardar_mensaje(user.id, user.username, nombre, "💬 Seleccionó hablar con soporte", "sistema")
        bot.edit_message_text(
            "💬 *SOPORTE*\n\nEscríbeme tu consulta.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=crear_menu_navegacion(),
            parse_mode='Markdown'
        )
    
    elif data == "retiro":
        guardar_mensaje(user.id, user.username, nombre, "💸 Solicitó hacer un retiro", "sistema")
        bot.edit_message_text(
            "💸 *RETIRO*\n\nEnvíame:\n✅ Monto\n✅ CBU/Alias\n✅ Titular",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=crear_menu_navegacion(),
            parse_mode='Markdown'
        )
    
    elif data == "faq":
        guardar_mensaje(user.id, user.username, nombre, "❓ Consultó preguntas frecuentes", "sistema")
        bot.edit_message_text(
            "❓ *FAQ*\n\n¿Cuánto tarda? → Inmediato\n¿Mínimo? → $1,000",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=crear_menu_navegacion(),
            parse_mode='Markdown'
        )

def run_bot():
    print("🤖 Bot de Telegram iniciado")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

# ============= PANEL WEB CON FLASK =============

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_secreto_aqui'
socketio = SocketIO(app, cors_allowed_origins="*")

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Panel Admin - Telegram Bot</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #0f1419;
            color: #e7e9ea;
            height: 100vh;
            display: flex;
        }
        .sidebar {
            width: 350px;
            background: #16191e;
            border-right: 1px solid #2f3336;
            display: flex;
            flex-direction: column;
        }
        .header {
            padding: 20px;
            border-bottom: 1px solid #2f3336;
        }
        .header h1 {
            font-size: 20px;
            margin-bottom: 15px;
            color: #1d9bf0;
        }
        .stats {
            display: flex;
            gap: 15px;
        }
        .stat {
            flex: 1;
            text-align: center;
            padding: 10px;
            background: #1e2228;
            border-radius: 8px;
        }
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            display: block;
        }
        .stat-label {
            font-size: 11px;
            color: #71767b;
            text-transform: uppercase;
            margin-top: 4px;
        }
        .filters {
            display: flex;
            gap: 5px;
            padding: 15px;
            border-bottom: 1px solid #2f3336;
        }
        .filter-btn {
            flex: 1;
            padding: 8px;
            background: #1e2228;
            border: none;
            color: #e7e9ea;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }
        .filter-btn:hover {
            background: #2a2e35;
        }
        .filter-btn.active {
            background: #1d9bf0;
            color: white;
        }
        .conversations-list {
            flex: 1;
            overflow-y: auto;
        }
        .conversation {
            padding: 15px 20px;
            border-bottom: 1px solid #2f3336;
            cursor: pointer;
            transition: background 0.2s;
            position: relative;
        }
        .conversation:hover {
            background: #1e2228;
        }
        .conversation.active {
            background: #1e2228;
            border-left: 3px solid #1d9bf0;
        }
        .conversation-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
        }
        .avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: linear-gradient(135deg, #1d9bf0, #7856ff);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 16px;
        }
        .conversation-info {
            flex: 1;
        }
        .conversation-name {
            font-weight: 600;
            font-size: 15px;
        }
        .conversation-time {
            font-size: 12px;
            color: #71767b;
        }
        .status-badge {
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .status-nuevo { background: #ff4444; color: white; }
        .status-pendiente { background: #ffa500; color: white; }
        .status-cerrado { background: #4caf50; color: white; }
        .message-count-badge {
            min-width: 28px;
            height: 28px;
            padding: 4px 8px;
            background: #1d9bf0;
            color: white;
            border-radius: 50%;
            font-size: 13px;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .message-preview {
            display: block;
            font-size: 13px;
            color: #71767b;
            font-weight: 400;
            margin-top: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .conversation-preview {
            font-size: 13px;
            color: #71767b;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .chat-area {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: #0f1419;
        }
        .chat-header {
            padding: 15px 20px;
            border-bottom: 1px solid #2f3336;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .chat-user-info {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .chat-actions {
            display: flex;
            gap: 8px;
        }
        .action-btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .btn-pendiente {
            background: #ffa500;
            color: white;
        }
        .btn-cerrar {
            background: #4caf50;
            color: white;
        }
        .action-btn:hover {
            opacity: 0.9;
            transform: translateY(-1px);
        }
        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .message {
            max-width: 70%;
            padding: 12px 16px;
            border-radius: 18px;
            font-size: 14px;
            line-height: 1.5;
            word-wrap: break-word;
        }
        .message img {
            cursor: pointer;
            transition: transform 0.2s;
        }
        .message img:hover {
            transform: scale(1.02);
        }
        .message-usuario {
            align-self: flex-start;
            background: #1e2228;
            color: #e7e9ea;
        }
        .message-admin {
            align-self: flex-end;
            background: #1d9bf0;
            color: white;
        }
        .message-sistema {
            align-self: center;
            background: #2f3336;
            color: #71767b;
            font-size: 12px;
            font-style: italic;
            padding: 8px 14px;
            border-radius: 12px;
        }
        .message-sistema::before {
            content: "ℹ️ ";
            margin-right: 4px;
        }
        .message-time {
            font-size: 11px;
            opacity: 0.7;
            margin-top: 4px;
        }
        .message-input-area {
            padding: 15px 20px;
            border-top: 1px solid #2f3336;
            display: flex;
            gap: 10px;
        }
        .message-input {
            flex: 1;
            padding: 12px 16px;
            background: #1e2228;
            border: 1px solid #2f3336;
            border-radius: 24px;
            color: #e7e9ea;
            font-size: 14px;
            outline: none;
            resize: none;
            max-height: 120px;
        }
        .message-input:focus {
            border-color: #1d9bf0;
        }
        .send-btn {
            padding: 12px 24px;
            background: #1d9bf0;
            border: none;
            border-radius: 24px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .send-btn:hover {
            background: #1a8cd8;
        }
        .send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .empty-state {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            gap: 15px;
            color: #71767b;
        }
        .empty-state-icon {
            font-size: 64px;
        }
        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #16191e;
        }
        ::-webkit-scrollbar-thumb {
            background: #2f3336;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #4a4e54;
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="header">
            <h1>🎯 Panel de Administración</h1>
            <div class="stats">
                <div class="stat">
                    <span class="stat-number" id="stat-nuevos">0</span>
                    <span class="stat-label">Nuevos</span>
                </div>
                <div class="stat">
                    <span class="stat-number" id="stat-pendientes">0</span>
                    <span class="stat-label">Pendientes</span>
                </div>
                <div class="stat">
                    <span class="stat-number" id="stat-cerrados">0</span>
                    <span class="stat-label">Cerrados</span>
                </div>
            </div>
        </div>
        
        <div class="filters">
            <button class="filter-btn active" data-filter="todos">Todos</button>
            <button class="filter-btn" data-filter="nuevo">Nuevos</button>
            <button class="filter-btn" data-filter="pendiente">Pendientes</button>
            <button class="filter-btn" data-filter="cerrado">Cerrados</button>
        </div>
        
        <div class="conversations-list" id="conversations-list"></div>
    </div>
    
    <div class="chat-area">
        <div class="chat-header" id="chat-header" style="display: none;">
            <div class="chat-user-info">
                <div class="avatar" id="chat-avatar">JP</div>
                <div>
                    <div class="conversation-name" id="chat-name">Usuario</div>
                    <div class="conversation-time" id="chat-username">@username</div>
                </div>
            </div>
            <div class="chat-actions">
                <button class="action-btn btn-pendiente" onclick="cambiarEstado('pendiente')">Marcar Pendiente</button>
                <button class="action-btn btn-cerrar" onclick="cambiarEstado('cerrado')">Cerrar</button>
                <button class="action-btn" style="background: #1d9bf0; color: white;" onclick="cambiarEstado('nuevo')">Reabrir</button>
            </div>
        </div>
        
        <div class="messages-container" id="messages-container">
            <div class="empty-state">
                <div class="empty-state-icon">💬</div>
                <div>Selecciona una conversación para ver los mensajes</div>
            </div>
        </div>
        
        <div class="message-input-area" id="message-input-area" style="display: none;">
            <textarea 
                class="message-input" 
                id="message-input" 
                placeholder="Escribe tu respuesta..."
                rows="1"
            ></textarea>
            <button class="send-btn" onclick="enviarMensaje()">Enviar</button>
        </div>
    </div>

    <script>
        const socket = io();
        let conversacionActual = null;
        let filtroActual = 'todos';

        // Cargar conversaciones
        async function cargarConversaciones() {
            const response = await fetch('/api/conversaciones');
            const conversaciones = await response.json();
            
            const container = document.getElementById('conversations-list');
            container.innerHTML = '';
            
            const filtradas = conversaciones.filter(conv => {
                if (filtroActual === 'todos') return true;
                return conv.estado === filtroActual;
            });
            
            filtradas.forEach(conv => {
                const div = document.createElement('div');
                div.className = `conversation ${conversacionActual === conv.user_id ? 'active' : ''}`;
                div.onclick = () => seleccionarConversacion(conv.user_id, conv.nombre, conv.username);
                
                const iniciales = conv.nombre.substring(0, 2).toUpperCase();
                const tiempo = formatearTiempo(conv.ultimo_mensaje);
                
                // Obtener preview del último mensaje
                const preview = conv.ultimo_mensaje_texto || 'Sin mensajes';
                const previewCorto = preview.length > 50 ? preview.substring(0, 50) + '...' : preview;
                
                div.innerHTML = `
                    <div class="conversation-header">
                        <div class="avatar">${iniciales}</div>
                        <div class="conversation-info">
                            <div class="conversation-name">
                                ${conv.nombre}
                                <span class="message-preview">${previewCorto}</span>
                            </div>
                            <div class="conversation-time">${tiempo}</div>
                        </div>
                        <span class="message-count-badge">${conv.total_mensajes}</span>
                    </div>
                `;
                
                container.appendChild(div);
            });
        }

        // Seleccionar conversación
        async function seleccionarConversacion(userId, nombre, username) {
            conversacionActual = userId;
            
            document.getElementById('chat-header').style.display = 'flex';
            document.getElementById('message-input-area').style.display = 'flex';
            document.getElementById('chat-name').textContent = nombre;
            document.getElementById('chat-username').textContent = username ? `@${username}` : '';
            document.getElementById('chat-avatar').textContent = nombre.substring(0, 2).toUpperCase();
            
            await cargarMensajes();
            cargarConversaciones();
        }

        // Cargar mensajes de la conversación actual
        async function cargarMensajes() {
            if (!conversacionActual) return;
            
            const response = await fetch(`/api/mensajes/${conversacionActual}`);
            const mensajes = await response.json();
            
            const container = document.getElementById('messages-container');
            const scrollEstabaPorDebajo = container.scrollHeight - container.scrollTop <= container.clientHeight + 100;
            
            container.innerHTML = '';
            
            mensajes.forEach(msg => {
                const div = document.createElement('div');
                div.className = `message message-${msg.tipo}`;
                
                let contenido = '';
                
                // Debug: mostrar info en consola
                console.log('Mensaje:', msg);
                
                // Si es una imagen, mostrarla
                if (msg.media_type === 'image' && msg.media_path) {
                    console.log('Cargando imagen:', msg.media_path);
                    contenido = `
                        <img src="/${msg.media_path}" alt="Imagen" style="max-width: 300px; max-height: 300px; border-radius: 12px; display: block; margin-bottom: 8px;" onerror="console.error('Error cargando imagen:', this.src)">
                        ${msg.mensaje ? `<div>${msg.mensaje}</div>` : ''}
                    `;
                } else if (msg.tipo === 'sistema') {
                    // Mensajes del sistema con estilo destacado
                    contenido = `<strong>${msg.mensaje}</strong>`;
                } else {
                    contenido = msg.mensaje;
                }
                
                div.innerHTML = `
                    ${contenido}
                    <div class="message-time">${formatearTiempo(msg.timestamp)}</div>
                `;
                container.appendChild(div);
            });
            
            // Auto-scroll solo si ya estaba abajo
            if (scrollEstabaPorDebajo) {
                container.scrollTop = container.scrollHeight;
            }
        }

        // Enviar mensaje
        async function enviarMensaje() {
            const input = document.getElementById('message-input');
            const mensaje = input.value.trim();
            
            if (!mensaje || !conversacionActual) return;
            
            await fetch('/api/enviar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: conversacionActual,
                    mensaje: mensaje
                })
            });
            
            input.value = '';
            await cargarMensajes();
        }

        // Auto-actualizar mensajes cada 2 segundos
        let intervalActualizacion = null;
        
        function iniciarAutoActualizacion() {
            if (intervalActualizacion) {
                clearInterval(intervalActualizacion);
            }
            
            intervalActualizacion = setInterval(async () => {
                if (conversacionActual) {
                    await cargarMensajes();
                }
                await cargarConversaciones();
                await cargarEstadisticas();
            }, 2000); // Actualiza cada 2 segundos
        }

        // Cambiar estado
        async function cambiarEstado(nuevoEstado) {
            if (!conversacionActual) return;
            
            await fetch('/api/cambiar_estado', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: conversacionActual,
                    estado: nuevoEstado
                })
            });
            
            cargarConversaciones();
            cargarEstadisticas();
        }

        // Cargar estadísticas
        async function cargarEstadisticas() {
            const response = await fetch('/api/stats');
            const stats = await response.json();
            
            document.getElementById('stat-nuevos').textContent = stats.nuevos;
            document.getElementById('stat-pendientes').textContent = stats.pendientes;
            document.getElementById('stat-cerrados').textContent = stats.cerrados;
        }

        // Formatear tiempo
        function formatearTiempo(timestamp) {
            if (!timestamp) return '';
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now - date;
            
            if (diff < 60000) return 'Ahora';
            if (diff < 3600000) return `${Math.floor(diff/60000)}m`;
            if (diff < 86400000) return `${Math.floor(diff/3600000)}h`;
            return `${Math.floor(diff/86400000)}d`;
        }

        // Filtros
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                filtroActual = this.dataset.filter;
                cargarConversaciones();
            });
        });

        // Enter para enviar
        document.getElementById('message-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                enviarMensaje();
            }
        });

        // WebSocket
        socket.on('nuevo_mensaje', function(data) {
            // Reproducir sonido de notificación
            reproducirNotificacion();
            
            if (data.user_id === conversacionActual && data.tipo === 'usuario') {
                cargarMensajes();
            }
            cargarConversaciones();
            cargarEstadisticas();
        });

        socket.on('estado_actualizado', function(data) {
            cargarConversaciones();
            cargarEstadisticas();
        });

        // Función para reproducir sonido de notificación
        function reproducirNotificacion() {
            // Crear sonido simple con Web Audio API
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.value = 800;
            oscillator.type = 'sine';
            
            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.5);
            
            // También mostrar notificación del navegador si tiene permiso
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification('Nuevo mensaje', {
                    body: 'Has recibido un nuevo mensaje',
                    icon: '📩'
                });
            }
        }

        // Solicitar permiso para notificaciones
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }

        // Inicializar
        cargarConversaciones();
        cargarEstadisticas();
        iniciarAutoActualizacion(); // Activar auto-actualización
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/media/<path:path>')
def serve_media(path):
    return send_from_directory('media', path)

@app.route('/api/conversaciones')
def get_conversaciones():
    conn = sqlite3.connect('bot_messages.db', check_same_thread=False)
    c = conn.cursor()
    
    # Mostrar conversaciones de las últimas 24 horas mínimo
    c.execute('''SELECT c.id, c.user_id, c.username, c.nombre, c.estado,
                        COUNT(m.id) as total_mensajes,
                        MAX(m.timestamp) as ultimo_mensaje,
                        (SELECT mensaje FROM mensajes WHERE conversacion_id = c.id ORDER BY timestamp DESC LIMIT 1) as ultimo_mensaje_texto
                 FROM conversaciones c
                 LEFT JOIN mensajes m ON c.id = m.conversacion_id
                 WHERE datetime(c.updated_at) >= datetime('now', '-1 day')
                    OR c.estado != 'cerrado'
                 GROUP BY c.id
                 ORDER BY ultimo_mensaje DESC''')
    
    conversaciones = []
    for row in c.fetchall():
        conversaciones.append({
            'id': row[0],
            'user_id': row[1],
            'username': row[2],
            'nombre': row[3],
            'estado': row[4],
            'total_mensajes': row[5],
            'ultimo_mensaje': row[6],
            'ultimo_mensaje_texto': row[7] if len(row) > 7 else ''
        })
    
    conn.close()
    return jsonify(conversaciones)

@app.route('/api/mensajes/<int:user_id>')
def get_mensajes(user_id):
    conn = sqlite3.connect('bot_messages.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute('SELECT id FROM conversaciones WHERE user_id = ?', (user_id,))
    resultado = c.fetchone()
    
    if not resultado:
        return jsonify([])
    
    conv_id = resultado[0]
    
    c.execute('''SELECT m.mensaje, m.tipo, m.timestamp, m.media_type, m.media_path
                 FROM mensajes m
                 WHERE m.conversacion_id = ?
                 ORDER BY m.timestamp ASC''', (conv_id,))
    
    mensajes = []
    for row in c.fetchall():
        mensajes.append({
            'mensaje': row[0],
            'tipo': row[1],
            'timestamp': row[2],
            'media_type': row[3],
            'media_path': row[4]
        })
    
    conn.close()
    return jsonify(mensajes)

@app.route('/api/enviar', methods=['POST'])
def enviar_mensaje():
    data = request.json
    user_id = data.get('user_id')
    mensaje = data.get('mensaje')
    
    if not user_id or not mensaje:
        return jsonify({'error': 'Faltan datos'}), 400
    
    try:
        # Enviar mensaje por Telegram
        bot.send_message(
            chat_id=user_id,
            text=f"💬 *Respuesta del Admin:*\n\n{mensaje}",
            reply_markup=crear_menu_navegacion(),
            parse_mode='Markdown'
        )
        
        # Guardar en BD
        guardar_mensaje(user_id, None, None, mensaje, "admin")
        print(f"✅ Mensaje enviado a usuario {user_id}")
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cambiar_estado', methods=['POST'])
def cambiar_estado():
    data = request.json
    user_id = data.get('user_id')
    nuevo_estado = data.get('estado')
    
    conn = sqlite3.connect('bot_messages.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('UPDATE conversaciones SET estado = ? WHERE user_id = ?', (nuevo_estado, user_id))
    conn.commit()
    conn.close()
    
    socketio.emit('estado_actualizado', {'user_id': user_id, 'estado': nuevo_estado})
    print(f"✅ Estado cambiado a '{nuevo_estado}' para usuario {user_id}")
    
    return jsonify({'success': True})

@app.route('/api/stats')
def get_stats():
    conn = sqlite3.connect('bot_messages.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM conversaciones WHERE estado = "nuevo"')
    nuevos = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM conversaciones WHERE estado = "pendiente"')
    pendientes = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM conversaciones WHERE estado = "cerrado"')
    cerrados = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'nuevos': nuevos,
        'pendientes': pendientes,
        'cerrados': cerrados
    })

# ============= WEBHOOK MERCADOPAGO =============

@app.route('/webhook/mercadopago', methods=['POST'])
def webhook_mercadopago():
    """Recibe notificaciones de MercadoPago cuando se completa un pago"""
    
    data = request.json
    print(f"📩 Webhook recibido de MercadoPago: {data}")
    
    # MercadoPago envía el tipo de notificación
    if data.get('type') == 'payment':
        payment_id = data.get('data', {}).get('id')
        
        if payment_id:
            # Consultar información del pago
            url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
            headers = {"Authorization": f"Bearer {MERCADOPAGO_ACCESS_TOKEN}"}
            
            try:
                response = requests.get(url, headers=headers)
                payment_data = response.json()
                
                user_id = int(payment_data.get('external_reference', 0))
                status = payment_data.get('status')
                
                # Actualizar estado del pago en BD
                conn = sqlite3.connect('bot_messages.db', check_same_thread=False)
                c = conn.cursor()
                c.execute('''UPDATE pagos SET estado = ?, payment_id = ?, updated_at = CURRENT_TIMESTAMP
                             WHERE user_id = ? AND estado = 'pending' ''', (status, payment_id, user_id))
                conn.commit()
                conn.close()
                
                # Si el pago fue aprobado, enviar el CBU al usuario
                if status == 'approved':
                    cbu = "0170059540000007890123"
                    alias = "NEGOCIO.DIGITAL.MP"
                    
                    mensaje = (
                        f"✅ *PAGO CONFIRMADO*\n\n"
                        f"Tu pago de $1,000 fue aprobado.\n\n"
                        f"💳 *DATOS PARA TRANSFERIR*\n\n"
                        f"📋 *CBU:* `{cbu}`\n"
                        f"🏷️ *Alias:* `{alias}`"
                    )
                    
                    bot.send_message(
                        chat_id=user_id,
                        text=mensaje,
                        parse_mode='Markdown',
                        reply_markup=crear_menu_navegacion()
                    )
                    
                    # Registrar en conversación
                    guardar_mensaje(user_id, None, None, "✅ Pago aprobado - CBU enviado", "sistema")
                    print(f"✅ Pago aprobado para usuario {user_id}")
                
                elif status == 'rejected':
                    bot.send_message(
                        chat_id=user_id,
                        text="❌ *PAGO RECHAZADO*\n\nTu pago fue rechazado. Por favor, intenta nuevamente.",
                        parse_mode='Markdown',
                        reply_markup=crear_menu_principal()
                    )
                    print(f"❌ Pago rechazado para usuario {user_id}")
                
            except Exception as e:
                print(f"❌ Error procesando webhook: {e}")
    
    return jsonify({'status': 'ok'}), 200

@app.route('/pago/success')
def pago_success():
    return "<h1>✅ Pago exitoso!</h1><p>En breve recibirás los datos en el bot de Telegram.</p>"

@app.route('/pago/failure')
def pago_failure():
    return "<h1>❌ Pago rechazado</h1><p>Por favor, intenta nuevamente desde el bot.</p>"

@app.route('/pago/pending')
def pago_pending():
    return "<h1>⏳ Pago pendiente</h1><p>Tu pago está siendo procesado.</p>"

# ============= INICIAR TODO =============

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 INICIANDO SISTEMA COMPLETO")
    print("="*60)
    
    # Inicializar BD
    init_db()
    print("✅ Base de datos inicializada")
    
    # Iniciar bot en thread separado
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    print(f"\n🌐 Panel Web: http://localhost:{FLASK_PORT}")
    print("="*60 + "\n")
    
    # Iniciar servidor web
    socketio.run(app, host='0.0.0.0', port=FLASK_PORT, debug=False, allow_unsafe_werkzeug=True)
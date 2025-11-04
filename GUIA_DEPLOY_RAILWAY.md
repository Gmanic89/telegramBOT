# 🚂 GUÍA COMPLETA: DESPLEGAR BOT EN RAILWAY

## 📋 Archivos necesarios

Descarga TODOS estos archivos y colócalos en tu carpeta `C:\Users\u632414\Desktop\bot`:

1. ✅ bot_server.py (actualizado)
2. ✅ requirements.txt
3. ✅ Procfile
4. ✅ runtime.txt
5. ✅ .gitignore

---

## 🚀 PASO 1: Crear cuenta en Railway

1. Ve a: https://railway.app
2. Haz clic en **"Start a New Project"** o **"Login"**
3. Inicia sesión con **GitHub** (es la forma más fácil)
   - Si no tienes GitHub, créate una cuenta en: https://github.com

---

## 🐙 PASO 2: Subir tu código a GitHub

### Opción A: Usar GitHub Desktop (MÁS FÁCIL)

1. **Descarga GitHub Desktop:**
   - Ve a: https://desktop.github.com
   - Descarga e instala

2. **Abre GitHub Desktop:**
   - Inicia sesión con tu cuenta de GitHub

3. **Crear repositorio:**
   - File → New Repository
   - Name: `telegram-bot-mercadopago`
   - Local Path: `C:\Users\u632414\Desktop\bot`
   - Haz clic en "Create Repository"

4. **Publicar en GitHub:**
   - Haz clic en "Publish repository"
   - Desmarca "Keep this code private" (o déjalo privado, como prefieras)
   - Haz clic en "Publish repository"

### Opción B: Usar Git desde terminal

```bash
cd C:\Users\u632414\Desktop\bot

# Inicializar git
git init

# Agregar todos los archivos
git add .

# Hacer commit
git commit -m "Initial commit"

# Crear repositorio en GitHub y seguir instrucciones
```

---

## 🚂 PASO 3: Desplegar en Railway

1. **Ve a Railway:**
   - https://railway.app/dashboard

2. **Nuevo proyecto:**
   - Haz clic en **"New Project"**
   - Selecciona **"Deploy from GitHub repo"**

3. **Selecciona tu repositorio:**
   - Busca `telegram-bot-mercadopago`
   - Haz clic en el repositorio

4. **Railway detectará automáticamente:**
   - Python
   - requirements.txt
   - Procfile
   - ¡Empezará a hacer deploy! 🎉

---

## ⚙️ PASO 4: Configurar Variables de Entorno

1. **En Railway, ve a tu proyecto**

2. **Haz clic en "Variables"**

3. **Agrega estas variables:**

```
BOT_TOKEN=8432915259:AAEOFgo5nvNhmiJEz6GNd-U3QQIY5xvRP_8
MERCADOPAGO_ACCESS_TOKEN=TU_ACCESS_TOKEN_DE_MERCADOPAGO
```

4. **Railway agregará automáticamente:**
   - `PORT` (el puerto que usará)
   - `RAILWAY_PUBLIC_DOMAIN` (tu dominio público)

---

## 🌐 PASO 5: Obtener tu URL pública

1. **En Railway, ve a "Settings"**

2. **Busca la sección "Domains"**

3. **Haz clic en "Generate Domain"**

4. **Copia tu URL:**
   - Se verá como: `tu-proyecto.up.railway.app`
   - Ejemplo: `telegram-bot-mercadopago-production.up.railway.app`

---

## ✅ PASO 6: Verificar que funciona

1. **Revisa los logs en Railway:**
   - Deberías ver:
   ```
   🚀 INICIANDO SISTEMA COMPLETO
   ✅ Base de datos inicializada
   🤖 Bot de Telegram iniciado
   ```

2. **Prueba tu bot:**
   - Abre Telegram
   - Envía `/start` a tu bot
   - ¡Debería funcionar! 🎉

3. **Prueba el panel admin:**
   - Ve a: `https://tu-proyecto.up.railway.app`
   - Deberías ver tu panel de administración

---

## 🎯 VENTAJAS DE RAILWAY

✅ **Gratis** (hasta $5 USD de crédito mensual - suficiente para este bot)
✅ **URL fija** (no cambia como ngrok)
✅ **Online 24/7**
✅ **Dominio HTTPS automático**
✅ **Webhooks de MercadoPago funcionarán perfectamente**
✅ **No necesitas ngrok nunca más**
✅ **Logs en tiempo real**
✅ **Fácil de actualizar** (solo haces push a GitHub)

---

## 🔄 ACTUALIZAR TU BOT (después del deploy)

Cuando quieras actualizar tu bot:

1. **Edita tu código localmente**
2. **En GitHub Desktop:**
   - Verás los cambios
   - Escribe un mensaje de commit (ej: "Agregué nueva función")
   - Haz clic en "Commit to main"
   - Haz clic en "Push origin"
3. **Railway detectará los cambios y hará redeploy automáticamente** 🚀

---

## 💰 COSTOS DE RAILWAY

**Plan Gratuito (Hobby):**
- $5 USD de crédito mensual
- Tu bot usa aprox. $0.50-2 USD/mes
- **Suficiente para empezar** 🎉

**Plan Paid (si creces):**
- $5 USD/mes por $5 de crédito + $0.000231/GB-hour
- Solo si necesitas más recursos

---

## 🆘 TROUBLESHOOTING

### El bot no inicia:
- Revisa los logs en Railway
- Verifica que las variables de entorno estén correctas
- Verifica que `requirements.txt` tenga todas las librerías

### El webhook no funciona:
- Verifica que `RAILWAY_PUBLIC_DOMAIN` esté en las variables
- Espera 2-3 minutos después del deploy
- Revisa los logs cuando hagas un pago de prueba

### La base de datos se borra:
- Railway usa almacenamiento efímero
- Solución: Agrega Railway PostgreSQL o SQLite persistente
- Te puedo ayudar con esto después

---

## 📞 PRÓXIMOS PASOS

Una vez desplegado:

1. ✅ Ya no necesitas ngrok
2. ✅ Tu bot estará online 24/7
3. ✅ Tendrás una URL fija
4. ✅ Los webhooks de MercadoPago funcionarán perfectamente
5. ✅ Panel admin accesible desde cualquier lugar

---

## 🎓 RESUMEN

```bash
# 1. Sube tu código a GitHub (usa GitHub Desktop)
# 2. Conecta Railway con tu repositorio de GitHub
# 3. Configura variables de entorno en Railway
# 4. Railway desplegará automáticamente
# 5. ¡Listo! Tu bot está en producción 🚀
```

**Tiempo estimado:** 10-15 minutos

---

¿Necesitas ayuda en algún paso específico? ¡Avísame! 🚀

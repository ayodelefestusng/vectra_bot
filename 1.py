2026-04-12 20:22:18,143 [INFO] uvicorn.error:shutdown:67 - Waiting for application shutdown.
2026-04-12 20:22:18,144 [INFO] uvicorn.error:shutdown:76 - Application shutdown complete.
2026-04-12 20:22:18,145 [INFO] uvicorn.error:_serve:102 - Finished server process [1]

2026-04-12 20:22:25,242 [DEBUG] matplotlib:wrapper:342 - matplotlib data path: /app/.venv/lib/python3.13/site-packages/matplotlib/mpl-data
2026-04-12 20:22:25,248 [DEBUG] matplotlib:wrapper:342 - CONFIGDIR=/root/.config/matplotlib
2026-04-12 20:22:25,249 [DEBUG] matplotlib:<module>:1560 - interactive is False
2026-04-12 20:22:25,249 [DEBUG] matplotlib:<module>:1561 - platform is linux
2026-04-12 20:22:25,465 [DEBUG] matplotlib:wrapper:342 - CACHEDIR=/root/.cache/matplotlib
2026-04-12 20:22:25,465 [DEBUG] matplotlib.font_manager:__init__:1085 - font search path [PosixPath('/app/.venv/lib/python3.13/site-packages/matplotlib/mpl-data/fonts/ttf'), PosixPath('/app/.venv/lib/python3.13/site-packages/matplotlib/mpl-data/fonts/afm'), PosixPath('/app/.venv/lib/python3.13/site-packages/matplotlib/mpl-data/fonts/pdfcorefonts')]
2026-04-12 20:22:25,632 [INFO] matplotlib.font_manager:_load_fontmanager:1639 - generated new fontManager
2026-04-12 20:22:26,673 [INFO] HR_AGENT:log_info:27 - [Tenant: sudo_tenant_id | Conversation: sudo_conversation_id] _get_access_token  called
2026-04-12 20:22:26,675 [DEBUG] urllib3.connectionpool:_new_conn:1049 - Starting new HTTPS connection (1): api-devapps.vfdbank.systems:443
2026-04-12 20:22:27,181 [DEBUG] urllib3.connectionpool:_make_request:544 - https://api-devapps.vfdbank.systems:443 "POST /vfd-tech/baas-portal/v1.1/baasauth/token HTTP/1.1" 200 None
2026-04-12 20:22:27,242 [INFO] HR_AGENT:log_info:27 - [Tenant: sytem | Conversation: sytem] Attempting to create instance: instagram_bot
2026-04-12 20:22:27,243 [DEBUG] urllib3.connectionpool:_new_conn:1049 - Starting new HTTPS connection (1): whatsapp-1-evolution-api.xqqhik.easypanel.host:443
2026-04-12 20:22:27,431 [DEBUG] urllib3.connectionpool:_make_request:544 - https://whatsapp-1-evolution-api.xqqhik.easypanel.host:443 "POST /instance/create HTTP/1.1" 400 83
2026-04-12 20:22:27,432 [ERROR] HR_AGENT:log_error:30 - [Tenant: system | Conversation: system] Failed to create instance. Status: 400, Response: {'status': 400, 'error': 'Bad Request', 'response': {'message': ['Invalid integration']}}
2026-04-12 20:22:27,436 [DEBUG] urllib3.connectionpool:_new_conn:1049 - Starting new HTTPS connection (1): whatsapp-1-evolution-api.xqqhik.easypanel.host:443
2026-04-12 20:22:27,459 [DEBUG] urllib3.connectionpool:_make_request:544 - https://whatsapp-1-evolution-api.xqqhik.easypanel.host:443 "POST /webhook/set/instagram_bot HTTP/1.1" 404 107
2026-04-12 20:22:27,459 [ERROR] root:setup_webhookv1:374 - Failed to set webhook. Status: 404
2026-04-12 20:22:27,460 [ERROR] root:setup_webhookv1:375 - Response: {'status': 404, 'error': 'Not Found', 'response': {'message': ['The "instagram_bot" instance does not exist']}}
             Importing from /
 
    module   📁 app            
             ├── 🐍 __init__.py
             └── 🐍 main.py    
 
      code   Importing the FastAPI app object from the module with the following
             code:                                                              
 
             from app.main import app
 
       app   Using import string: app.main:app
 
    server   Server started at http://0.0.0.0:80
    server   Documentation at http://0.0.0.0:80/docs
 
             Logs:
 
      INFO   Started server process [1]
2026-04-12 20:22:27,559 [INFO] uvicorn.error:_serve:92 - Started server process [1]
2026-04-12 20:22:27,560 [INFO] uvicorn.error:startup:48 - Waiting for application startup.
      INFO   Waiting for application startup.
      INFO   Application startup complete.
2026-04-12 20:22:27,561 [INFO] uvicorn.error:startup:62 - Application startup complete.
      INFO   Uvicorn running on http://0.0.0.0:80 (Press CTRL+C to quit)
2026-04-12 20:22:27,562 [INFO] uvicorn.error:_log_started_message:224 - Uvicorn running on http://0.0.0.0:80 (Press CTRL+C to quit)

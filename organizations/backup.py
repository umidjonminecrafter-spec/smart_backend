import os
import json
import tempfile
import zipfile
import datetime
import urllib.request
import urllib.error
import mimetypes
import uuid
from django.apps import apps
from django.core import serializers
from django.utils import timezone

def send_via_bot(bot_token, chat_id, file_path, filename):
    """
    Sends a file as a document via Telegram Bot API using urllib.request.
    """
    boundary = uuid.uuid4().hex
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
    except Exception as e:
        return False, f"Faylni o'qishda xatolik: {str(e)}"
        
    lines = []
    
    # Add chat_id parameter
    lines.extend([
        f"--{boundary}".encode('utf-8'),
        b'Content-Disposition: form-data; name="chat_id"',
        b'',
        str(chat_id).encode('utf-8')
    ])
    
    # Add document parameter
    mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
    lines.extend([
        f"--{boundary}".encode('utf-8'),
        f'Content-Disposition: form-data; name="document"; filename="{filename}"'.encode('utf-8'),
        f'Content-Type: {mime_type}'.encode('utf-8'),
        b'',
        file_content
    ])
    
    # End boundary
    lines.extend([
        f"--{boundary}--".encode('utf-8'),
        b''
    ])
    
    body = b'\r\n'.join(lines)
    
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body))
    }
    
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            res_body = response.read()
            res_json = json.loads(res_body.decode('utf-8'))
            if res_json.get('ok'):
                return True, "Yuborildi"
            else:
                return False, res_json.get('description', "Noma'lum xatolik")
    except urllib.error.URLError as e:

        return False, f"Telegram tarmoq xatoligi: {str(e)}"
    except Exception as e:
        return False, f"Kutilmagan xatolik: {str(e)}"

def send_via_userbot(api_id, api_hash, session_string, chat_id, file_path, filename):
    """
    Sends a file via Userbot using telethon (if installed).
    """
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        import asyncio
        
        async def main():
            try:
                appid = int(api_id)
            except ValueError:
                return False, "API ID butun son bo'lishi kerak."
                
            client = TelegramClient(StringSession(session_string), appid, api_hash)
            await client.connect()
            
            # Check authorization status
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "Userbot session string eskirgan yoki noto'g'ri."
                
            target_chat = chat_id
            if chat_id.isdigit() or (chat_id.startswith('-') and chat_id[1:].isdigit()):
                target_chat = int(chat_id)
                
            await client.send_file(
                target_chat, 
                file_path, 
                file_name=filename, 
                caption=f"SmartTalim Zaxira Nusxasi (Userbot)\nSana: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await client.disconnect()
            return True, "Yuborildi"

        # Safe execution of event loop in sync thread/view
        import threading
        result_container = []
        
        def run_async():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                res, msg = new_loop.run_until_complete(main())
                result_container.append((res, msg))
            except Exception as ex:
                result_container.append((False, str(ex)))
            finally:
                new_loop.close()
                
        t = threading.Thread(target=run_async)
        t.start()
        t.join()
        
        if result_container:
            return result_container[0]
        return False, "Userbot ishga tushirish jarayoni javobsiz qoldi."
            
    except ImportError:
        return False, "Tizimda 'telethon' kutubxonasi o'rnatilmagan. Iltimos, serverda 'pip install telethon' bajaring."
    except Exception as e:
        return False, f"Userbot xatoligi: {str(e)}"

def run_backup_for_setting(setting):
    """
    Performs organization data backup and uploads it via Telegram.
    """
    org = setting.organization
    org_id = org.id
    
    # 1. Gather all tenant data
    backup_data = []
    
    for model in apps.get_models():
        # Check if the model has organization field
        field_names = [f.name for f in model._meta.fields]
        if 'organization' in field_names:
            try:
                queryset = model.objects.filter(organization_id=org_id)
                if queryset.exists():
                    serialized_str = serializers.serialize('json', queryset)
                    serialized_list = json.loads(serialized_str)
                    backup_data.extend(serialized_list)
            except Exception as e:
                # Log model serialization failures but don't abort completely
                print(f"Error serializing model {model.__name__} in backup: {str(e)}")
                
    if not backup_data:
        return False, "Zaxiralash uchun hech qanday ma'lumot topilmadi."

    # 2. Setup temporary paths
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Clean org name for filename
    org_name_clean = "".join(c for c in org.name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    json_filename = f"backup_{org_name_clean}_{timestamp}.json"
    zip_filename = f"backup_{org_name_clean}_{timestamp}.zip"
    
    temp_dir = tempfile.mkdtemp()
    json_path = os.path.join(temp_dir, json_filename)
    zip_path = os.path.join(temp_dir, zip_filename)
    
    try:
        # Write JSON data
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
        # Create ZIP
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(json_path, json_filename)
            
        # 3. Send to Telegram
        success = False
        errors = []
        
        # Method A: Bot API (Preferred if configured)
        if setting.bot_token and setting.chat_id:
            bot_success, bot_msg = send_via_bot(setting.bot_token, setting.chat_id, zip_path, zip_filename)
            if bot_success:
                success = True
            else:
                errors.append(f"Bot API: {bot_msg}")
                
        # Method B: Userbot (Alternative)
        if not success and setting.api_id and setting.api_hash and setting.session_string and setting.chat_id:
            userbot_success, userbot_msg = send_via_userbot(
                setting.api_id, setting.api_hash, setting.session_string, setting.chat_id, zip_path, zip_filename
            )
            if userbot_success:
                success = True
            else:
                errors.append(f"Userbot API: {userbot_msg}")
                
        if not success:
            error_details = ", ".join(errors) if errors else "Telegram sozlamalari to'ldirilmagan."
            return False, f"Jo'natib bo'lmadi ({error_details})"
            
        # Update last run timestamp
        setting.last_run_at = timezone.now()
        setting.save(update_fields=['last_run_at'])
        
        return True, "Zaxira nusxasi muvaffaqiyatli yuborildi! ✅"
        
    except Exception as e:
        return False, f"Zaxiralash tizimi xatosi: {str(e)}"
        
    finally:
        # Cleanup files safely
        try:
            if os.path.exists(json_path):
                os.remove(json_path)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            os.rmdir(temp_dir)
        except Exception:
            pass

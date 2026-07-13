import os
import requests
import json
from typing import List, Dict, Tuple


class LLMClient:
    @staticmethod
    def ask_ai(message: str, history: List[Dict[str, str]] = None) -> Tuple[str, float]:
        """
        Sends message to LLM (Gemini or OpenAI) with conversation history context.
        Returns a tuple: (response_text, confidence_score)
        """
        if history is None:
            history = []

        # 1. Try Gemini API (Free Tier available)
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
                headers = {"Content-Type": "application/json"}
                
                system_instruction = (
                    "You are an AI Support Assistant for a SaaS platform. "
                    "Help the user politely. "
                    "Along with your answer, evaluate your own confidence score "
                    "based on how well you resolved the user's issue. "
                    "Always output your response in JSON format matching this schema: "
                    '{"answer": "Your reply here...", "confidence": 0.85}'
                )
                
                context_str = ""
                for msg in history[-8:]:
                    role = "Assistant" if msg.get('sender') == 'ai' else "User"
                    context_str += f"{role}: {msg.get('content', '')}\n"
                
                prompt = f"{system_instruction}\n\nHistory:\n{context_str}\nUser: {message}\n"
                
                payload = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "responseMimeType": "application/json"
                    }
                }
                
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                if response.status_code == 200:
                    res_data = response.json()
                    raw_content = res_data['candidates'][0]['content']['parts'][0]['text']
                    parsed = json.loads(raw_content)
                    answer = parsed.get("answer", "")
                    confidence = float(parsed.get("confidence", 0.8))
                    return answer, confidence
            except Exception as e:
                print(f"Gemini API Error: {str(e)}")

        # 2. Try OpenAI API
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json"
                }
                
                messages = [{"role": "system", "content": (
                    "You are an AI Support Assistant for a SaaS platform. "
                    "Help the user politely. "
                    "Along with your answer, you MUST evaluate your own confidence score "
                    "based on how well you resolved the user's issue. "
                    "Always output your response in JSON format like this: "
                    '{"answer": "Your reply here...", "confidence": 0.85}'
                )}]
                
                for msg in history[-10:]:
                    role = "user" if msg.get('sender') == 'user' else "assistant"
                    messages.append({"role": role, "content": msg.get('content', '')})
                    
                messages.append({"role": "user", "content": message})
                
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2
                }
                
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                if response.status_code == 200:
                    res_data = response.json()
                    raw_content = res_data['choices'][0]['message']['content']
                    parsed = json.loads(raw_content)
                    answer = parsed.get("answer", "")
                    confidence = float(parsed.get("confidence", 0.8))
                    return answer, confidence
            except Exception as e:
                print(f"OpenAI API Error: {str(e)}")

        # 3. Mock mode for testing / local execution when API keys are missing
        msg_lower = message.lower()
        if "operator" in msg_lower or "bog'lanish" in msg_lower or "inson" in msg_lower or "xodim" in msg_lower:
            return "Sizni operatorga ulayapman. Iltimos kuting...", 0.1
        elif "salom" in msg_lower or "hello" in msg_lower:
            return "Assalomu alaykum! Sizga qanday yordam bera olaman?", 0.95
        else:
            return f"Bu sizning '{message}' xabaringizga sun'iy intellekt tomonidan qaytarilgan avtomatik javob. Agarda muammoingiz hal bo'lmasa, operator bilan bog'lanish deb yozing.", 0.75

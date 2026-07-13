import os
import requests
import json
from typing import List, Dict, Tuple


class LLMClient:
    @staticmethod
    def ask_ai(message: str, history: List[Dict[str, str]] = None) -> Tuple[str, float]:
        """
        Sends message to LLM (OpenAI) with conversation history context.
        Returns a tuple: (response_text, confidence_score)
        """
        if history is None:
            history = []

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Mock mode for testing / local execution when API key is missing
            msg_lower = message.lower()
            if "operator" in msg_lower or "bog'lanish" in msg_lower or "inson" in msg_lower or "xodim" in msg_lower:
                return "Sizni operatorga ulayapman. Iltimos kuting...", 0.1
            elif "salom" in msg_lower or "hello" in msg_lower:
                return "Assalomu alaykum! Sizga qanday yordam bera olaman?", 0.95
            else:
                return f"Bu sizning '{message}' xabaringizga sun'iy intellekt tomonidan qaytarilgan avtomatik javob. Agarda muammoingiz hal bo'lmasa, operator bilan bog'lanish deb yozing.", 0.75

        # Production Mode: OpenAI API Call
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
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
            
            for msg in history[-10:]:  # Keep last 10 messages for context
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
            # Safe logging
            print(f"LLM API Error: {str(e)}")
            
        return "Tizimda vaqtincha uzilish yuz berdi. Operatorlarimiz siz bilan bog'lanishadi.", 0.2

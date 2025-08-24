from groq import Groq
from langchain_core.runnables import RunnableLambda

def create_diagnostic_agent(api_key: str):
    try:
        client = Groq(api_key=api_key)

        def run_gemma_chat(inputs: dict) -> str:
            # Handle both dictionary inputs and message objects
            if isinstance(inputs, dict):
                system_prompt = inputs.get("system_prompt", "")
                user_input = inputs.get("input", "")
                context = inputs.get("context", "")
                chat_history = inputs.get("chat_history", [])
            else:
                try:
                    # Handle LangChain message objects
                    if hasattr(inputs, 'messages'):
                        messages = inputs.messages
                    elif isinstance(inputs, list):
                        messages = inputs
                    else:
                        messages = [inputs]

                    system_prompt = ""
                    user_input = ""
                    context = ""
                    chat_history = []

                    for msg in messages:
                        if hasattr(msg, 'type'):  # LangChain message type
                            if msg.type == "system":
                                system_prompt = msg.content
                            elif msg.type == "human":
                                user_input = msg.content
                            elif msg.type == "ai":
                                chat_history.append({"role": "assistant", "content": msg.content})
                        elif hasattr(msg, 'role'):  # OpenAI-style message
                            if msg.role == "system":
                                system_prompt = msg.content
                            elif msg.role == "user":
                                user_input = msg.content
                            elif msg.role == "assistant":
                                chat_history.append({"role": "assistant", "content": msg.content})
                except Exception as e:
                    print(f"Error processing non-dict input: {e}")
                    return "I'm having trouble processing your request. Please try again."

            messages = [{"role": "system", "content": system_prompt}]
            for msg in chat_history[-4:]:  # Keep last 4 messages as context
                messages.append({"role": msg["role"], "content": msg["content"]})

            messages.append({"role": "user", "content": f"{user_input}\n\n{context}"})

            try:
                response = client.chat.completions.create(
                    model="gemma2-9b-it",
                    messages=messages,
                    temperature=0.8,
                    top_p=1,
                    max_completion_tokens=1024,
                    stream=False
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"Error in diagnostic agent: {e}")
                return "I'm having trouble processing your request. Please try again."

        return RunnableLambda(run_gemma_chat)
    except Exception as e:
        print(f"Failed to initialize diagnostic agent: {e}")
        return RunnableLambda(lambda x: "Diagnostic service is currently unavailable")
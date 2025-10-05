import requests
import sys
import json
from support_functions import jade_color, reset_color, db_credentials, profile_path
from sql_worker import sqlcoder_reasoning


#API test and pre-load
try:
    #test API connection
    request = requests.get("http://localhost:11434/api/tags", timeout=5)
    if request.status_code == 200:
        pass #API works
    else: 
        print("\n Couldn't connnet to Jade API. Status: ", request.status_code, "\n")
        sys.exit(1)

    #load phi-3 to RAM
    print("\nLoading model into the memory...")
    warmup_message = {'role': 'user', 'content': 'Say simple "Hi"'}

    with requests.post("http://localhost:11434/api/chat",
                        json={"model": "phi3", "messages": [warmup_message],
                        "stream": True},
                        timeout=180) as warmup:
        model_ready = False
        for line in warmup.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8")) #responses come as json so need to decode
                if "message" in data and "content" in data["message"]:
                    model_ready = True
                    break

    if model_ready:
        print('\nJade is loaded. Type your question. Be a gentleman. Type /bye to exit.')
        print('If you want to ask database related questions - start your prompt with "!SQL" phrase')
        print('Treat each database question as a separate case. Do not refer to the previous results\n')
    else:
        print("Couldn't load the Phi-3 model")
        sys.exit(1)
except requests.exceptions.RequestException as exception:
    print("\n Error connecting to Jade API:", exception, "\n")
    sys.exit(1)


#setting up profile prompt
with open(profile_path, "r", encoding="utf-8") as profile:
    profile_prompt = profile.read().strip()

#conversation history to be re-send with every prompt. Each time trimmed to system_prompt + last 20 prompts
messages = [{"role": "system", "content": profile_prompt}]
history_limit = 20


# --- chat loop ---
while True:
    user_input = input("You: ").strip()

    #input to exit the chat
    if user_input.lower() == '/bye':
        print(f"{jade_color}\nJade: Goodbye!")
        break

    #checking each prompt if starts with !SQL, if so then treat as a question to sqlcoder
    sqlcoder_key_phrase = "!sql"
    if user_input.lower().strip().startswith(sqlcoder_key_phrase):
        customers = [] #customer names found in prompt
        for customer_name in db_credentials.keys():
            if customer_name.lower() in user_input.lower():
                customers.append(customer_name)

        if len(customers) == 1:
            customer = customers[0]
            plain_query = user_input.strip("!SQLsql").strip() #strip "!SQL" regardless of letter case
            sqlcoder_response = sqlcoder_reasoning(customer, plain_query) #and pass to SQLCoder
            messages.append({'role': 'user', 'content': f"""
                             The following question has been asked to the SQL reasoning tool:
                             \n"{plain_query}"\n
                             The query results from the tool are:
                             \n"{sqlcoder_response}"\n
                             Please show me the results in plain language"""}) #append the user prompt with query results

        elif len(customers) > 1:
            print(f"{jade_color}Specify a single customer name please.")
            break #LOGIC TO BE ADDED

        else:
            print(f"{jade_color}Specify the customer name please.")
            break #LOGIC TO BE ADDED

    else: #if no !SQL prompt then append user prompt as regular
        messages.append({"role": "user", "content": user_input})


    #to keep the history concise cutting only to last 20 prompts
    if len(messages) > history_limit:
        system_message = messages[0]
        recent_history = messages[-history_limit:] #to keep last 20 prompts
        messages = [system_message] + recent_history #to turn system_message into a list and add to recent_history list

    # --- prompt preview for debugging ---
    print(f"Messages in history: {len(messages)} including profile prompt")
    print(messages)
    # --- prompt preview for debugging ---


    # --- streaming chat ---
    with requests.post("http://localhost:11434/api/chat", 
                    json={"model": "phi3", "messages": messages, "stream": True},
                    stream=True) as chat_connection:
        
        jade_reply = ""
        first_token = True #marking the first token to add a new line and "Jade:"

        for line in chat_connection.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8")) #responses come as json so need to decode
                if "message" in data and "content" in data["message"]:
                    token = data["message"]["content"]

                    if first_token:
                        print(f"\n{jade_color}Jade: ", end="", flush=True) #to add new line and "Jade:" at the beginning of Jade prompt
                        first_token = False #so it no loger adds new line and "Jade:" for the rest of the tokens in single prompt

                    print(token, end="", flush=True)
                    jade_reply += token

        messages.append({"role": "assistant", "content": jade_reply.strip()})
        print(reset_color + "\n")
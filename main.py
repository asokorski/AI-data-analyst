import requests
import os
import sys
import json
from support_functions import jade_color, reset_color
from sql_worker import execute_query


#paths for profile and table_cards and setting up the system_prompt
jade_directory = os.path.dirname(os.path.abspath(__file__))
profile_path = os.path.join(jade_directory, "profile")
table_cards_path = os.path.join(jade_directory, "table_cards")

with open(profile_path, "r", encoding="utf-8") as profile:
    profile_prompt = profile.read().strip()

with open(table_cards_path, "r", encoding="utf-8") as table_cards:
    table_cards_prompt = table_cards.read().strip()

system_prompt = profile_prompt + "\n\nDatabase knowledge:\n" + table_cards_prompt


#test of API connection
try:
    request = requests.get("http://localhost:11434/api/tags", timeout=5)
    if request.status_code == 200:
        print("\n Jade is online. Type your question. Be a gentleman. Type /bye to exit \n")
    else:
        print("\n Couldn't connnet to Jade API. Status: ", request.status_code, "\n")
        sys.exit(1)
except requests.exceptions.RequestException as exception:
    print("\n Error connecting to Jade API:", exception, "\n")
    sys.exit(1)


#conversation history to be re-send with every prompt. Each time trimmed to system_prompt + last 20 prompts
messages = [{"role": "system", "content": system_prompt}]
history_limit = 20


# --- chat loop ---
while True:
    user_input = input("You: ")
    if user_input.lower() == '/bye':
        print(f"{jade_color}\nJade: Goodbye!")
        break

    #appends the user_input to the messages each time
    messages.append({"role": "user", "content": user_input})

    #to keep the history concise cutting only to last 20 prompts
    if len(messages) > history_limit:
        system_message = messages[0]
        recent_history = messages[-history_limit:] #to keep last 20 prompts
        messages = [system_message] + recent_history #to turn system_message into a list and add to recent_history list


    # --- prompt preview for debugging ---
    print(f"Messages in history: {len(messages)} including profile+table_cards")
    print(messages)
    # --- prompt preview for debugging ---

    # --- streaming chat ---
    with requests.post("http://localhost:11434/api/chat", 
                    json={"model": "phi3", "messages": messages, "stream": True},
                    stream=True) as chat_connection:
        
        jade_reply = ""
        first_token = True #marking the first token to add a new line and "#"

        for line in chat_connection.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8"))
                if "message" in data and "content" in data["message"]:
                    token = data["message"]["content"]

                    if first_token:
                        print(f"\n{jade_color}Jade: ", end="", flush=True) #to add new line and "#" at the beginning of Jade prompt
                        first_token = False #so it no loger adds new line and "#" for the rest of the tokens in single prompt

                    print(token, end="", flush=True)
                    jade_reply += token

        # --- after streaming finished, try to parse as JSON ---
        try:
            
            #sanitizing the output as Jade likes to reply with "```json" before generating json
            clean_reply = jade_reply.strip()
            if clean_reply.startswith("```"):
                clean_reply = clean_reply.strip("`") #removes `
                if clean_reply.startswith("json"):
                    clean_reply = clean_reply[4:].strip() #removes "json"

            parsed = json.loads(clean_reply) #parsing json into dictionary

            if isinstance(parsed, dict) and parsed.get("action") == "create_query": #double check if we got correct dict and action is "create_query"
                customer = parsed.get("customer")
                query = parsed.get("sql")
                print("Jade JSON query parsed correctly") #debugging

                #messages.append({"role": "assistant", "content": jade_reply.strip()}) #append Jade reply, crossed out to reduce the mess sent to Jade

                #running sql query
                status, results = execute_query(customer, query)
                if status == True:
                    tool_result = {
                        "tool": "query_result",
                        "status": "ok",
                        "customer": customer,
                        "row_count": len(results),
                        "results": results
                    }
                else:
                    tool_result = {
                        "tool": "query_result",
                        "status": "error",
                        "customer": customer,
                        "message": f"Database execution failed. Error: {results}",
                    }

                messages.append({"role": "assistant", "content": f"Tool: {json.dumps(tool_result)}"}) #append query results
                messages.append({"role": "user", "content": "Please summarize the tool results for me"}) #ask Jade to show results

                with requests.post("http://localhost:11434/api/chat", 
                    json={"model": "phi3", "messages": messages, "stream": True},
                    stream=True) as summary_connection:
                    
                    summary_reply = ""
                    first_token = True
                    for line in summary_connection.iter_lines():
                        if line:
                            data = json.loads(line.decode("utf-8"))
                            if "message" in data and "content" in data["message"]:
                                token = data["message"]["content"]

                                if first_token:
                                    print(f"\n{jade_color}Jade:", end="", flush=True)
                                    first_token = False

                                print(token, end="", flush=True)
                                summary_reply += token
                                messages.append({"role": "assistant", "content": summary_reply}) #append Jade reply with query results
                                
            else:
                #if it was JSON but not "create_query" append Jade reply
                messages.append({"role": "assistant", "content": jade_reply.strip()})

        except json.JSONDecodeError:
            #if jade_reply is not json then append Jade reply and proceed as normal 
            messages.append({"role": "assistant", "content": jade_reply.strip()})

        print(reset_color + "\n")
import oracledb as cx_Oracle
from support_functions import db_credentials, table_cards_path
import os
import json
import transformers
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
#silence warnings and progress bar
transformers.utils.logging.set_verbosity_error()
transformers.utils.logging.set_verbosity_error()
transformers.utils.logging.disable_progress_bar()


#loading the table_cards
with open(table_cards_path, "r", encoding="utf-8") as table_cards:
    table_cards_prompt = table_cards.read().strip()


#model configuration
MODEL_PATH = "./models/sqlcoder-7b"
_model = None
_tokenizer = None
_sqlgen = None


#load SQLCoder model and tokenizer once
def _load_sqlcoder():
    global _model, _tokenizer, _sqlgen

    if _sqlgen is None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

        print("Loading SQLCoder model into memory...")

        _tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, local_files_only=True)
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            local_files_only=True,
            device_map="cpu",
            dtype="auto")
        
        _sqlgen = pipeline(
            "text-generation",
            model=_model,
            tokenizer=_tokenizer,
            device_map="cpu")

    return _sqlgen


def execute_query(customer, query):
    try:
        credentials = db_credentials.get(customer.lower()) #depending on the customer
        if not credentials:
            return False, f"Unknown customer: {customer}"

        with cx_Oracle.connect(user=credentials["username"], password=credentials["password"], dsn=credentials["dsn"]) as connection:
            cursor = connection.cursor()
            cursor.execute(query)
            result = cursor.fetchall()
        return result
    
    except cx_Oracle.DatabaseError as error:
        return False, str(error)
    

#main function for reasoning
def sqlcoder_reasoning(customer, plain_query):
    sqlgen = _load_sqlcoder() #ensure that the model is loaded once

    prompt = f"""You are an expert Oracle SQL generator.
Return only SQL code - no explanations, no markdown, no commentary.

Database schema:
{table_cards_prompt}

User question:
{plain_query}
"""

    result = sqlgen(prompt, max_new_tokens=200, do_sample=False)[0]["generated_text"]

    #remove any prefix or markdown formatting to clean the output
    clean_sql = (result.replace("```sql", "").replace("```", "").replace("SQL:", "").strip())

    # Try to extract starting from first SQL keyword
    for keyword in ["SELECT", "WITH"]:
        idx = clean_sql.upper().find(keyword)
        if idx != -1:
            clean_sql = clean_sql[idx:]
            break

    decision = input(f"\n{clean_sql}\n\nDo you want to execute the query? ")
    if decision == "yes":
        return execute_query(customer, clean_sql)
    else:
        return False
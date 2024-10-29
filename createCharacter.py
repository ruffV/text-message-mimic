import sys
import sqlite3
import os
import torch
from transformers import GPT2LMHeadModel, GPT2Tokenizer, Trainer, TrainingArguments
from datasets import Dataset

phone_number = sys.argv[1]

db_path = os.path.expanduser('~/Library/Messages/chat.db')
conn = sqlite3.connect(db_path)

cursor=conn.cursor()

query = f"""
SELECT message.is_from_me, message.text
FROM message
JOIN handle ON message.handle_id = handle.ROWID
WHERE handle.id = '+1{phone_number}'
AND message.text IS NOT NULL
ORDER BY message.date ASC;
"""

cursor.execute(query)

results = cursor.fetchall()
with open('message_conversation.txt', 'w') as file:
    speaker=results[0][0]
    prev_speaker=results[0][0]
    message=str(results[0][0]) + ": "
    for row in results:
        if(row[1].startswith('Loved ')):
            continue
        
        speaker = row[0]
        if(speaker == prev_speaker):
            message += row[1] + ". "
        else:
            file.write(message + "\n")
            message = str(speaker) + ": " + row[1] + ". "
        prev_speaker = speaker

cursor.close()
conn.close()

print("Conversation Data gathered succesfully")


model_name = "gpt2"
tokenizer = GPT2Tokenizer.from_pretrained(model_name)
model = GPT2LMHeadModel.from_pretrained(model_name)

device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
print("running on: " + str(device))
model.to(device)

tokenizer.pad_token = tokenizer.eos_token
model.resize_token_embeddings(len(tokenizer))



def load_data(file_path):
    dialogues = []
    with open(file_path, 'r') as f:
        dialogue = ""
        for line in f.readlines():
            
            if(': ' not in line):
                continue
            if(len(line.strip().split(': ')) < 2):
                continue
            
            if line.startswith("1:"):
                dialogue += line.strip().split(": ")[1] + " <|endoftext|> "  # Add end token after user input
            elif line.startswith("0:"):
                dialogue += line.strip().split(": ")[1] + " <|endoftext|> "
                dialogues.append(dialogue.strip())
                dialogue = ""
    return dialogues

dialogues = load_data('message_conversation.txt')

def tokenize_data(dialogues):
    tokenized_dialogues = tokenizer(dialogues, return_tensors='pt', truncation=True, padding=True, max_length=128)
    input_ids = tokenized_dialogues['input_ids']
    
    labels = input_ids.clone()
    labels[labels == tokenizer.pad_token_id] = -100
    
    return {'input_ids': input_ids, 'attention_mask': tokenized_dialogues['attention_mask'], 'labels': labels}

tokenized_data = tokenize_data(dialogues)
dataset = Dataset.from_dict(tokenized_data)
print("Data tokenized succesfuly")

training_args = TrainingArguments(
    output_dir='./results',
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    logging_dir='./logs',
    logging_steps=10,
    save_steps=500,
    save_total_limit=2,
    evaluation_strategy="no",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
)

print("Began training loop(can take a little bit of time ~ 5-10 minutes)")
trainer.train()

print("Training loop complete")

model.save_pretrained("./character")
tokenizer.save_pretrained("./character")

print("Character created! To talk with them, run: python3 chat.py")
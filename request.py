import requests

def get_conversations():
    url = "http://localhost:8000/v1/list"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            conversations = []
            conversation_data = response.json().get("conversation_names", [])
            for idx, conversation in enumerate(conversation_data, start=1):
                conversations.append({"key": idx, "name": conversation})
            return conversations
        else:
            print("Failed to retrieve conversations. Status code:", response.status_code)
            return []
    except requests.exceptions.RequestException as e:
        print("An error occurred while retrieving conversations:", e)
        return []

def send_request():
    url = "http://localhost:8000/v1/text"
    conversations = get_conversations()
    conversation_name = None

    if conversations:
        print("Existing conversations:\n" + "\n".join((f"{conv["key"]}: {conv["name"]}") for conv in conversations))
        choice = input("Do you want to create a new conversation or select an existing one? (new/select): ").strip().lower()
        if choice == "select":
            try:
                selected_key = int(input("Enter the conversation key: ").strip())
                conversation_name = next((conv["name"] for conv in conversations if conv["key"] == selected_key), None)
                if conversation_name is None:
                    print("Invalid conversation key. Starting a new conversation.")
            except ValueError:
                print("Invalid input. Starting a new conversation.")
                conversation_name = None
    else:
        print("No existing conversations found. Starting a new conversation.")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Ending the conversation.")
            break

        payload = {"content": user_input}
        if conversation_name:
            payload["conversation_name"] = conversation_name

        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                response_data = response.json()
                conversation_name = response_data.get("conversation_name", conversation_name)
                print("Assistant:", response_data["content"])
            else:
                print("Failed to get a valid response. Status code:", response.status_code)
        except requests.exceptions.RequestException as e:
            print("An error occurred:", e)

if __name__ == "__main__":
    send_request()

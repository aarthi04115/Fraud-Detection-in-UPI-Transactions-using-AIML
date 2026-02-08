"""Test that chatbot maintains conversation context"""
import requests
import json
import time

def test_conversation():
    print("=" * 80)
    print("TESTING CHATBOT CONVERSATION HISTORY")
    print("=" * 80)
    
    base_url = "http://localhost:8000/api/chatbot"
    
    # Simulate a multi-turn conversation
    conversation_history = []
    
    # Turn 1: Greeting
    print("\n[Turn 1: Greeting]")
    msg1 = "Hello! Who are you?"
    print(f"User: {msg1}")
    
    r1 = requests.post(base_url, json={
        "message": msg1,
        "history": conversation_history
    }, timeout=15)
    
    response1 = r1.json()
    print(f"Bot Response: {response1['response'][:200]}...")
    
    conversation_history.append({"role": "user", "content": msg1})
    conversation_history.append({"role": "assistant", "content": response1['response']})
    
    time.sleep(1)
    
    # Turn 2: Follow-up question (should reference previous context)
    print("\n" + "=" * 80)
    print("[Turn 2: Follow-up without repeating]")
    msg2 = "Who are you again?"
    print(f"User: {msg2}")
    
    r2 = requests.post(base_url, json={
        "message": msg2,
        "history": conversation_history
    }, timeout=15)
    
    response2 = r2.json()
    print(f"Bot Response: {response2['response'][:200]}...")
    print(f"\n[CHECK] Does response differ from Turn 1? {response2['response'] != response1['response']}")
    
    conversation_history.append({"role": "user", "content": msg2})
    conversation_history.append({"role": "assistant", "content": response2['response']})
    
    time.sleep(1)
    
    # Turn 3: Transaction ID query
    print("\n" + "=" * 80)
    print("[Turn 3: Show transaction context]")
    msg3 = "How many transactions were blocked?"
    print(f"User: {msg3}")
    
    r3 = requests.post(base_url, json={
        "message": msg3,
        "history": conversation_history
    }, timeout=15)
    
    response3 = r3.json()
    print(f"Bot Response: {response3['response'][:250]}...")
    
    conversation_history.append({"role": "user", "content": msg3})
    conversation_history.append({"role": "assistant", "content": response3['response']})
    
    time.sleep(1)
    
    # Turn 4: Context-aware question
    print("\n" + "=" * 80)
    print("[Turn 4: Context-aware (should reference blocked transactions)]")
    msg4 = "Tell me more about the risk scores"
    print(f"User: {msg4}")
    
    r4 = requests.post(base_url, json={
        "message": msg4,
        "history": conversation_history
    }, timeout=15)
    
    response4 = r4.json()
    print(f"Bot Response: {response4['response'][:250]}...")
    
    print("\n" + "=" * 80)
    print("CONVERSATION FLOW TEST COMPLETE")
    print("=" * 80)
    
    # Summary
    print(f"\nTurn 1 Response Length: {len(response1['response'])} chars")
    print(f"Turn 2 Response Length: {len(response2['response'])} chars")
    print(f"Turn 3 Response Length: {len(response3['response'])} chars")
    print(f"Turn 4 Response Length: {len(response4['response'])} chars")
    
    print(f"\nResponses are unique: {len({response1['response'], response2['response'], response3['response'], response4['response']})}/4 unique")

if __name__ == "__main__":
    time.sleep(3)  # Wait for server to start
    test_conversation()

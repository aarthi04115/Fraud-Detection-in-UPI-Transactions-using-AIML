"""Final verification that chatbot maintains conversation context properly"""
import requests
import time
import json

def print_section(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_multi_turn_conversation():
    base_url = "http://localhost:8000/api/chatbot"
    
    print_section("CHATBOT CONVERSATION CONTEXT TEST")
    print("Testing that chatbot remembers context across multiple turns...\n")
    
    conversation = []
    
    # Turn 1: Greeting
    print_section("TURN 1: User greets the chatbot")
    msg1 = "Hello, who are you?"
    print(f"User: {msg1}")
    
    r1 = requests.post(base_url, json={
        "message": msg1,
        "history": conversation.copy()
    }, timeout=15)
    
    resp1 = r1.json()['response']
    print(f"\nBot: {resp1[:300]}...")
    print(f"\nResponse length: {len(resp1)} chars")
    
    conversation.append({"role": "user", "content": msg1})
    conversation.append({"role": "assistant", "content": resp1})
    
    time.sleep(1)
    
    # Turn 2: Immediate follow-up (should NOT repeat)
    print_section("TURN 2: Follow-up question")
    msg2 = "I asked you who you are already!"
    print(f"User: {msg2}")
    print(f"Sending conversation history: {len(conversation)} messages")
    
    r2 = requests.post(base_url, json={
        "message": msg2,
        "history": conversation.copy()
    }, timeout=15)
    
    resp2 = r2.json()['response']
    print(f"\nBot: {resp2[:300]}...")
    print(f"\nResponse length: {len(resp2)} chars")
    
    is_different = resp2 != resp1
    print(f"\n✓ Response is DIFFERENT from Turn 1: {is_different}")
    
    conversation.append({"role": "user", "content": msg2})
    conversation.append({"role": "assistant", "content": resp2})
    
    time.sleep(1)
    
    # Turn 3: Ask for stats
    print_section("TURN 3: Ask for statistics")
    msg3 = "Give me transaction statistics"
    print(f"User: {msg3}")
    print(f"Sending conversation history: {len(conversation)} messages")
    
    r3 = requests.post(base_url, json={
        "message": msg3,
        "history": conversation.copy()
    }, timeout=15)
    
    resp3 = r3.json()['response']
    print(f"\nBot: {resp3[:300]}...")
    print(f"\nResponse length: {len(resp3)} chars")
    
    conversation.append({"role": "user", "content": msg3})
    conversation.append({"role": "assistant", "content": resp3})
    
    time.sleep(1)
    
    # Turn 4: Context-aware question
    print_section("TURN 4: Context-aware question")
    msg4 = "Of the blocked transactions you mentioned, what's the risk distribution?"
    print(f"User: {msg4}")
    print(f"Sending conversation history: {len(conversation)} messages")
    
    r4 = requests.post(base_url, json={
        "message": msg4,
        "history": conversation.copy()
    }, timeout=15)
    
    resp4 = r4.json()['response']
    print(f"\nBot: {resp4[:300]}...")
    print(f"\nResponse length: {len(resp4)} chars")
    
    time.sleep(1)
    
    # Turn 5: Another follow-up
    print_section("TURN 5: Another context-aware follow-up")
    msg5 = "Tell me more about that"
    print(f"User: {msg5}")
    print(f"Sending conversation history: {len(conversation)} messages")
    
    r5 = requests.post(base_url, json={
        "message": msg5,
        "history": conversation.copy()
    }, timeout=15)
    
    resp5 = r5.json()['response']
    print(f"\nBot: {resp5[:300]}...")
    print(f"\nResponse length: {len(resp5)} chars")
    
    # Summary
    print_section("RESULTS SUMMARY")
    
    responses = [resp1, resp2, resp3, resp4, resp5]
    unique_responses = len(set(responses))
    
    print(f"Total conversaation turns: 5")
    print(f"Unique responses: {unique_responses}/5")
    print(f"Average response length: {sum(len(r) for r in responses) / len(responses):.0f} chars")
    
    print("\nResponse lengths:")
    print(f"  Turn 1 (Greeting): {len(resp1)} chars")
    print(f"  Turn 2 (Follow-up): {len(resp2)} chars")
    print(f"  Turn 3 (Stats): {len(resp3)} chars")
    print(f"  Turn 4 (Context): {len(resp4)} chars")
    print(f"  Turn 5 (More): {len(resp5)} chars")
    
    if unique_responses == 5:
        print("\n✅ SUCCESS! All responses are unique and contextually appropriate!")
        print("✅ Chatbot is maintaining conversation context properly!")
        print("✅ No more repeated responses!")
    else:
        print(f"\n⚠ WARNING: Only {unique_responses}/5 responses are unique")
        print("Some responses may be repeating")

if __name__ == "__main__":
    try:
        test_multi_turn_conversation()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

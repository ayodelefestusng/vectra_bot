
import re
from langchain_core.messages import AIMessage, HumanMessage

def test_filtering_logic():
    print("--- Testing Filtering Logic in chat_bot.py (Simulated) ---")
    base64_data = "iVBORw0KGgoAAAANSUhEUgAAA90AAAJOCAYAAACqS2Tf..."
    raw_text = f"Here is your chart: ![Chart](data:image/png;base64,{base64_data})\nAnd some raw data: data:image/png;base64,{base64_data}"
    
    base64_pattern = r"!\[.*?\]\(data:image\/.*?;base64,.*?\)|data:image\/.*?;base64,[a-zA-Z0-9+/=]+"
    filtered_text = re.sub(base64_pattern, "[Image Visualization]", raw_text)
    
    print(f"Original text length: {len(raw_text)}")
    print(f"Filtered text: {filtered_text}")
    
    assert "[Image Visualization]" in filtered_text
    assert base64_data not in filtered_text
    print("Filtering logic test passed!\n")

def test_trimming_logic():
    print("--- Testing Trimming Logic in tools.py (Simulated) ---")
    base64_data = "A" * 200 # Longer than 100
    content = f"Check this image: data:image/png;base64,{base64_data}"
    msg = AIMessage(content=content)
    messages = [msg]
    
    base64_pattern = r"data:image\/.*?;base64,[a-zA-Z0-9+/=]{100,}"
    
    processed_messages = []
    for m in messages:
        if hasattr(m, "content") and isinstance(m.content, str) and re.search(base64_pattern, m.content):
            new_content = re.sub(base64_pattern, "[IMAGE_DATA_TRIMMED]", m.content)
            msg_type = type(m)
            processed_messages.append(msg_type(content=new_content))
        else:
            processed_messages.append(m)
            
    print(f"Original content length: {len(msg.content)}")
    print(f"Processed content: {processed_messages[0].content}")
    
    assert "[IMAGE_DATA_TRIMMED]" in processed_messages[0].content
    assert base64_data not in processed_messages[0].content
    print("Trimming logic test passed!")

if __name__ == "__main__":
    test_filtering_logic()
    test_trimming_logic()

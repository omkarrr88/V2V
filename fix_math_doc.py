import re

def validate_math_doc():
    try:
        with open('Mathematical_Model_V2V_BSD.md', 'r', encoding='utf-8') as f:
            text = f.read()
            
        issues = []
        if text.count('**Angle Convention:** All heading angles') > 1:
            issues.append("Duplication found: Angle Convention")
        if text.count('### 5.2.1 Lateral Time-To-Collision') > 1:
            issues.append("Duplication found: Section 5.2.1")
        if 'F1=0.0004' in text:
            issues.append("Outdated metric found: F1=0.0004")
            
        if not issues:
            print("✅ Mathematical Model passes automated formatting checks.")
        else:
            print("⚠️ Validation issues found in Mathematical_Model_V2V_BSD.md:")
            for i in issues:
                print(f"  - {i}")
                
    except FileNotFoundError:
        print("Mathematical_Model_V2V_BSD.md not found.")

if __name__ == "__main__":
    validate_math_doc()

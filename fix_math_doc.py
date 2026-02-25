import re

with open('Mathematical_Model_V2V_BSD.md', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix idempotency duplication of "**Angle Convention:** All heading angles"
while text.count('**Angle Convention:** All heading angles') > 1:
    text = re.sub(r'\n\n\*\*Angle Convention:\*\* All heading angles.*?(?=\*\*Angle Convention:\*\* All heading angles)', '', text, count=1, flags=re.DOTALL)

# Fix idempotency duplication of "### 5.2.1 Lateral Time-To-Collision"
while text.count('### 5.2.1 Lateral Time-To-Collision') > 1:
    idx_first = text.find('### 5.2.1 Lateral Time-To-Collision')
    idx_second = text.find('### 5.2.1 Lateral Time-To-Collision', idx_first + 1)
    if idx_second != -1:
        text = text[:idx_second]

# Fix v_lat_rel formula in Section 5.2.1
text = text.replace(r'v_{lat, rel} = v_e \cdot \sin(\theta_e - \theta_t)', r'v_{lat, rel} = v_t \cdot \sin(\theta_t - \theta_e)')
text = text.replace(r'v_e \cdot \sin(\theta_e - \theta_t)', r'v_t \cdot \sin(\theta_t - \theta_e)')

# Remove F1=0.0004
text = text.replace('Grid search, F1=0.0004', 'Grid search, composite near-miss optimized')
text = text.replace('| $\alpha$ ($R_{decel}$) | 0.35 | 0.15 | Grid search, F1=0.0004 |', '| $\alpha$ ($R_{decel}$) | 0.35 | 0.15 | Grid search, composite near-miss |')

# Explain centripetal deceleration limitation
limitation = '- **Centripetal Deceleration Ignored:** §4.2 dead reckoning utilizes constant linear acceleration. On curved roads, $a_t$ includes strong centripetal components that do not contribute to longitudinal stopping distance, causing errors under braking in curves.'
if 'Centripetal' not in text:
    text = text.replace('3.  **Elevation changes** (hills, ramps):', f'{limitation}\n3.  **Elevation changes** (hills, ramps):')

with open('Mathematical_Model_V2V_BSD.md', 'w', encoding='utf-8') as f:
    f.write(text)

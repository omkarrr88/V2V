import xml.etree.ElementTree as ET  

tree = ET.parse('../Maps/atal.net.xml')  
root = tree.getroot()  
connections = []  
for conn in root.findall('.//connection'):  
    from_id = conn.get('from')  
    to_id = conn.get('to')  
    connections.append(f"{from_id} -> {to_id}")  
with open('../Outputs/connections.txt', 'w') as f:  
    f.write('\n'.join(sorted(set(connections))))  # Unique, sorted  
print(f"Extracted {len(connections)} connections to Outputs/connections.txt.")  
print("Sample chains: Look for sequences like 'edgeA -> edgeB -> edgeC' in the file.")  
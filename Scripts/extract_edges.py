import xml.etree.ElementTree as ET

tree = ET.parse('../Maps/atal.net.xml')
edges = [edge.get('id') for edge in tree.findall('.//edge')]
with open('../Outputs/edges.txt', 'w') as f:
    f.write('\n'.join(sorted(edges)))
print(f"Extracted {len(edges)} edges. See Outputs/edges.txt for list (e.g., gneE0, gneE1...).")
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

f = open(r'[USER_HOME]\.claude\projects\C--Users-izeak-OneDrive-Work-Oki-toki-Monitoring-of-competitors\daded8f4-79ba-4216-8397-b0e3d6e6ee3a\tool-results\mcp-n8n-flexible-n8n_get_workflow-1766740172691.txt', 'r', encoding='utf-8')
data = json.load(f)
wf = json.loads(data[0]['text'])

print("=" * 60)
print(f"WORKFLOW: {wf['name']}")
print(f"ID: {wf['id']}")
print(f"Active: {wf['active']}")
print(f"Updated: {wf['updatedAt']}")
print("=" * 60)

print("\n=== NODES ===")
nodes = wf['nodes']
for i, n in enumerate(nodes, 1):
    node_type = n['type'].split('.')[-1]
    disabled = " [DISABLED]" if n.get('disabled') else ""
    print(f"{i:2}. {n['name'][:45]:<45} ({node_type}){disabled}")

print("\n=== CONNECTIONS ===")
connections = wf.get('connections', {})
for src, targets in connections.items():
    for output_type, conns in targets.items():
        for conn_list in conns:
            for conn in conn_list:
                target = conn.get('node', 'Unknown')
                print(f"  {src[:35]:<35} -> {target}")

print("\n=== WORKFLOW FLOW ===")
# Find trigger
triggers = [n for n in nodes if 'trigger' in n['type'].lower() or 'Trigger' in n['name']]
for t in triggers:
    print(f"START: {t['name']}")

# Find disabled nodes
disabled = [n for n in nodes if n.get('disabled')]
if disabled:
    print("\nDISABLED NODES:")
    for n in disabled:
        print(f"  - {n['name']}")

# Count node types
print("\n=== NODE TYPES SUMMARY ===")
types = {}
for n in nodes:
    t = n['type'].split('.')[-1]
    types[t] = types.get(t, 0) + 1
for t, c in sorted(types.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c}")

# Check for credentials used
print("\n=== CREDENTIALS USED ===")
for n in nodes:
    if 'credentials' in n:
        for cred_type, cred_info in n['credentials'].items():
            print(f"  {n['name']}: {cred_type} - {cred_info.get('name', 'unnamed')}")


import urllib.request, json

payload = json.dumps({
    'incident_number': 'INC0001234',
    'short_description': 'Payment API pods OOMKilled - heap space exhausted',
    'description': 'Multiple payment-api pods restarting with exit code 137',
    'category': 'memory',
    'priority': '1 - Critical',
    'logs': 'java.lang.OutOfMemoryError: Java heap space\nOOMKilled exit code 137\nHTTP 503',
    'recent_changes': 'Heap reduced from -Xmx4g to -Xmx2g',
    'application': 'payment-api',
    'environment': 'production'
}).encode()

req = urllib.request.Request(
    'http://localhost:8000/api/incidents/analyze',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
resp = urllib.request.urlopen(req)
result = json.loads(resp.read())
print('Root cause:', result['probable_root_cause'][:100])
print('Confidence:', result['confidence_label'], f"({result['confidence_score']:.0%})")
print('Team:', result['recommended_team'])
print('Mode:', result['analysis_mode'])
print('Similar cases:', len(result['similar_cases']))
print('Evidence signals:', len(result['evidence']))
print('Actions:', len(result['recommended_actions']))
print('Commands:', len(result['diagnostic_commands']))
print()
print('TEST PASSED')


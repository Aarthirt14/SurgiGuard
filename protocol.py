"""Versioned, unapproved simulation fixture. Never use as a clinical checklist."""
import re
VERSION = 'SG-SIM-02-draft'
ROLES = ('Surgeon', 'Anaesthetist', 'Nurse')
ITEMS = [
 dict(id='team',title='Team introductions',role='Nurse',expected='All team members introduced by name and role.',patterns=[r'\bintroduced\b',r'\bintroductions complete\b']),
 dict(id='identity',title='Patient, procedure & site',role='Surgeon',expected='Patient Alex Morgan, elective procedure, left side confirmed.',patterns=[r'alex morgan.*elective.*left.*confirmed']),
 dict(id='surgeon',title='Surgeon’s anticipated concerns',role='Surgeon',expected='Surgeon concerns reviewed with the team.',patterns=[r'surgeon.*concerns.*reviewed']),
 dict(id='anaesthesia',title='Anaesthesia concerns',role='Anaesthetist',expected='Anaesthesia concerns reviewed with the team.',patterns=[r'ana?esthe(?:sia|tic).*concerns.*reviewed']),
 dict(id='sterility',title='Sterility & equipment readiness',role='Nurse',expected='Sterility and equipment readiness verified.',patterns=[r'sterility.*equipment.*verified']),
 dict(id='review',title='Prophylaxis & imaging review',role='Surgeon',expected='Prophylaxis and imaging checklist fields reviewed.',patterns=[r'prophylaxis.*imaging.*reviewed'])
]
for index, item in enumerate(ITEMS): item['source'] = f'{VERSION} §{index+1}'

def assess(item, text, role, confidence, kind):
    if kind in ('overlap','interruption'):
        return 'flag', 'Interrupted or overlapping speech. Item context retained; please repeat one speaker at a time.'
    if kind == 'omission': return 'flag', f'No response recorded. Ask the {item["role"]} to respond.'
    if confidence is None or confidence < .85: return 'flag', 'Recognition is uncertain. Please repeat; nothing has been confirmed.'
    if role != item['role']: return 'flag', f'Role mismatch. Please ask the designated {item["role"]}.'
    if re.search(r"\b(not|no|never|uncertain|unconfirmed|wrong|right|isn.t|wasn.t|haven.t|hasn.t|don.t|didn.t)\b", text, re.I):
        return 'flag', 'Negative or contradictory evidence. Resolve the discrepancy, then submit corrected evidence.'
    if not any(re.search(p, text, re.I) for p in item['patterns']):
        return 'flag', 'Evidence does not match this bounded protocol item. Please clarify using the displayed expected response.'
    return 'pending', f'Evidence captured. The designated {item["role"]} must explicitly confirm.'

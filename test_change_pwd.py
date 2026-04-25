import sys
from pathlib import Path
sys.path.insert(0, str(Path('/Users/admin/Desktop/InsightsDSA_v2/src')))
from insightsdsa.app import app, get_session
from insightsdsa.models import User

with app.app_context():
    with app.test_client() as client:
        # 1. Get CSRF token first
        res_csrf = client.get('/api/v1/csrf')
        csrf_token = res_csrf.json['csrf_token']
        headers = {'X-CSRFToken': csrf_token}

        # 2. Login
        res = client.post('/login', json={'username': 'testuser', 'userpass': 'password'}, headers=headers)
        print("Login status:", res.status_code)

        if res.status_code != 200:
            with get_session() as s:
                u = s.query(User).filter_by(username='testuser').first()
                if not u:
                    from werkzeug.security import generate_password_hash
                    u = User(username='testuser', userpassword=generate_password_hash('password'))
                    s.add(u)
                    s.commit()
                res = client.post('/login', json={'username': 'testuser', 'userpass': 'password'}, headers=headers)
                print("Login retry status:", res.status_code)

        # 3. Change password
        res_change = client.post('/api/change-password', json={
            'current_password': 'password',
            'new_password': 'newpassword123'
        }, headers=headers)
        
        print("Change Password status:", res_change.status_code)
        print("Change Password response:", res_change.data.decode('utf-8'))


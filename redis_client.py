import redis

r = redis.Redis(host='52.57.134.177', port=6379, db=0, password='OAJUHyc1cLJwZ1nd8Ha8qM', username='default')
print(r.get('dlr:block:212687311502'))
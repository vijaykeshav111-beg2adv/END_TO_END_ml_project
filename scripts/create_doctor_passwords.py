from routers.auth import hash_password

password = "Doctor@123"

print(hash_password(password))
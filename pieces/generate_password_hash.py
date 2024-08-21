import bcrypt

def hash_password(plain_password):
    # Generate a salt and hash the password
    hashed = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8')

if __name__ == "__main__":
    plain_password = input("Enter the password to hash: ")
    hashed_password = hash_password(plain_password)
    print(f"Hashed password: {hashed_password}")

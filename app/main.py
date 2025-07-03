from repos.DbRepo import DbRepo

if __name__ == "__main__":
    repo = DbRepo()
    result = repo.execute("SELECT 1;")
    print(f"Query result: {result}")

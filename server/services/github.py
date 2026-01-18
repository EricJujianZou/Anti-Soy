import httpx
import os
from dotenv import load_dotenv

# Load .env from the server directory explicitly
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

class GitHubGraphQLClient:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.endpoint = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def execute_query(self, query: str, variables: dict = None):
        if not self.token or "placeholder" in self.token:
             # Fallback for testing without token if needed, or raise error
             pass 
             
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.endpoint,
                json={"query": query, "variables": variables},
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def fetch_user_data(self, username: str):
        query = """
        query($username: String!) {
          user(login: $username) {
            login
            url
            createdAt
            repositories(first: 5, orderBy: {field: PUSHED_AT, direction: DESC}, isFork: false) {
              nodes {
                name
                url
                stargazerCount
                isFork
                primaryLanguage {
                  name
                }
                languages(first: 10) {
                  nodes {
                    name
                  }
                }
                defaultBranchRef {
                  target {
                    ... on Commit {
                      history(first: 100) {
                        nodes {
                          committedDate
                          additions
                          deletions
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        result = await self.execute_query(query, {"username": username})
        if "errors" in result:
             raise Exception(f"GitHub API Error: {result['errors']}")
        return result.get("data", {}).get("user")

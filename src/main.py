import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from azure.identity.aio import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.users.users_request_builder import UsersRequestBuilder

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path.as_posix())

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

async def main():
    if not TENANT_ID or not CLIENT_ID or not CLIENT_SECRET:
        raise ValueError("Missing TENANT_ID, CLIENT_ID, or CLIENT_SECRET in .env file")

    credential = ClientSecretCredential(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )

    try:
        scopes = ["https://graph.microsoft.com/.default"]
        client = GraphServiceClient(credentials=credential, scopes=scopes)

        query_params = UsersRequestBuilder.UsersRequestBuilderGetQueryParameters(
            select=["id", "displayName", "userPrincipalName", "accountEnabled"],
            top=5
        )

        request_config = UsersRequestBuilder.UsersRequestBuilderGetRequestConfiguration(
            query_parameters=query_params
        )

        result = await client.users.get(request_configuration=request_config)

        users_output = []
        if result and result.value:
            for user in result.value:
                users_output.append({
                    "id": user.id,
                    "displayName": user.display_name,
                    "userPrincipalName": user.user_principal_name,
                    "accountEnabled": user.account_enabled
                })

        print(f"Success: wrote {len(users_output)} users to reports/users.json")

        os.makedirs("reports", exist_ok=True)

        await credential.close()
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
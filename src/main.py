import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from azure.identity.aio import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.users.users_request_builder import UsersRequestBuilder
from msgraph.generated.groups.groups_request_builder import GroupsRequestBuilder
from msgraph.generated.directory_roles.directory_roles_request_builder import DirectoryRolesRequestBuilder
#from msgraph.generated.directoryobjects.get_by_ids.get_by_ids_post_request_body import GetByIdsPostRequestBody

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

        with open("reports/users.json", "w", encoding="utf-8") as f:
            json.dump(users_output, f, indent=2)

        group_query_params = GroupsRequestBuilder.GroupsRequestBuilderGetQueryParameters(
            select=["id", "displayName", "mail", "securityEnabled"],
            top=5
        )

        group_request_config = GroupsRequestBuilder.GroupsRequestBuilderGetRequestConfiguration(
            query_parameters=group_query_params
        )

        group_result = await client.groups.get(request_configuration=group_request_config)

        groups_output = []
        if group_result and group_result.value:
            for group in group_result.value:
                groups_output.append({
                    "id": group.id,
                    "displayName": group.display_name,
                    "mail": group.mail,
                    "securityEnabled": group.security_enabled
                })

        with open("reports/groups.json", "w", encoding="utf-8") as f:
            json.dump(groups_output, f, indent=2)
        
                # Privileged directory roles
        role_query_params = DirectoryRolesRequestBuilder.DirectoryRolesRequestBuilderGetQueryParameters(
            select=["id", "displayName", "roleTemplateId"],
        )

        role_request_config = DirectoryRolesRequestBuilder.DirectoryRolesRequestBuilderGetRequestConfiguration(
            query_parameters=role_query_params
        )

        role_result = await client.directory_roles.get(request_configuration=role_request_config)

        privileged_roles_output = []
        if role_result and role_result.value:
            for role in role_result.value:
                if role.role_template_id:  # Only active roles
                    privileged_roles_output.append({
                        "id": role.id,
                        "displayName": role.display_name,
                        "roleTemplateId": role.role_template_id
                    })
#                    member_ids = set()
#
#                    for role in privileged_roles_output:
#                        for member in role["members"]:
#                            if member.get("id"):
#                                member_ids.add(member["id"])
#                            resolved_objects = {}
#
#                    if member_ids:
#                        request_body = GetByIdsPostRequestBody(
#                            ids=list(member_ids),
#                            types=["user", "group", "servicePrincipal", "device"]
#                        )
#
#                    directory_objects = await client.directory_objects.get_by_ids.post(request_body)
#
#                    if directory_objects and directory_objects.value:
#                        for obj in directory_objects.value:
#                            resolved_objects[obj.id] = {
#                                "id": obj.id,
#                                "type": obj.odata_type
#                            }
#                    for role in privileged_roles_output:
#                        enriched_members = []
#
#                        for member in role["members"]:
#                            resolved = resolved_objects.get(member["id"], {})
#
#                            enriched_members.append({
#                                "id": member["id"],
#                                "type": resolved.get("type", member.get("type")),
#                                "displayName": getattr(type("obj", (), resolved), "display_name", None)
#                            })
#
#                            role["members"] = enriched_members

        risk_findings = []

        member_role_map = {}

        for role in privileged_roles_output:
            role_name = role.get("displayName", "Unknown Role")
            members = role.get("members", [])

            member_count = len(members)

            if role_name == "Global Administrator" and member_count > 5:
                risk_findings.append({
                    "severity": "High",
                    "riskType": "TooManyGlobalAdmins",
                    "role": role_name,
                    "memberCount": member_count,
                    "reason": "Microsoft recommends fewer than 5 Global Administrators."
                })

            if member_count > 10:
                risk_findings.append({
                    "severity": "Medium",
                    "riskType": "TooManyPrivilegedMembers",
                    "role": role_name,
                    "memberCount": member_count,
                    "reason": "Microsoft recommends limiting the number of privileged role assignments."
                })

            if member_count == 0:
                risk_findings.append({
                    "severity": "Info",
                    "riskType": "EmptyPrivilegedRole",
                    "role": role_name,
                    "memberCount": member_count,
                    "reason": "Role has no active members."
                })

            for member in members:
                member_id = member.get("id")
                if member_id:
                    if member_id not in member_role_map:
                        member_role_map[member_id] = []

                    member_role_map[member_id].append(role_name)

        for member_id, roles in member_role_map.items():
            if len(roles) > 1:
                risk_findings.append({
                    "severity": "Medium",
                    "riskType": "MultiplePrivilegedRoles",
                    "memberId": member_id,
                    "roleCount": len(roles),
                    "roles": roles,
                    "reason": "Identity is assigned to multiple privileged roles."
                })

        with open("reports/risk_findings.json", "w", encoding="utf-8") as f:
            json.dump(risk_findings, f, indent=2)

        print(f"Success: wrote {len(risk_findings)} findings to reports/risk_findings.json")
        print(f"Success: wrote {len(users_output)} users to reports/users.json")
        print(f"Success: wrote {len(groups_output)} groups to reports/groups.json")
        print(f"Success: wrote {len(privileged_roles_output)} privileged roles to reports/privileged_roles.json")

        os.makedirs("reports", exist_ok=True)

        await credential.close()
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
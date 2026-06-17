import unittest

from fusbot_routing import (
    allowed_in_workspace_channel,
    build_roast_request,
)


class RoastRoutingTests(unittest.TestCase):
    def test_mentioned_target_becomes_roast_target_not_teller(self):
        request = build_roast_request(
            text="<@UBOT> roast <@UTARGET>",
            teller_user_id="UTELLER",
            bot_user_id="UBOT",
        )

        self.assertEqual(request.target_user_ids, ["UTARGET"])
        self.assertIn("UTARGET", request.prompt)
        self.assertIn("target", request.prompt.lower())
        self.assertNotIn("UTELLER", request.prompt)

    def test_explicit_target_prompt_does_not_roast_the_request_itself(self):
        request = build_roast_request(
            text="<@UBOT> roast <@UTARGET>",
            teller_user_id="UTELLER",
            bot_user_id="UBOT",
        )

        prompt = request.prompt.lower()
        self.assertNotIn("request context", prompt)
        self.assertNotIn("requester", prompt)
        self.assertNotIn("the request", prompt)

    def test_roast_without_target_falls_back_to_teller(self):
        request = build_roast_request(
            text="<@UBOT> roast me",
            teller_user_id="UTELLER",
            bot_user_id="UBOT",
        )

        self.assertEqual(request.target_user_ids, ["UTELLER"])
        self.assertIn("UTELLER", request.prompt)


class WorkspaceChannelPolicyTests(unittest.TestCase):
    def test_blocks_every_bot_response_outside_allowed_channel_in_workspace(self):
        self.assertFalse(
            allowed_in_workspace_channel(
                team_id="TWORK",
                enterprise_id="",
                channel_id="CWRONG",
                allowed_workspace_id="TWORK",
                allowed_channel_id="CALLOWED",
            )
        )

    def test_allows_configured_channel_and_other_workspaces(self):
        self.assertTrue(
            allowed_in_workspace_channel(
                team_id="TWORK",
                enterprise_id="",
                channel_id="CALLOWED",
                allowed_workspace_id="TWORK",
                allowed_channel_id="CALLOWED",
            )
        )
        self.assertTrue(
            allowed_in_workspace_channel(
                team_id="TOTHER",
                enterprise_id="",
                channel_id="CWRONG",
                allowed_workspace_id="TWORK",
                allowed_channel_id="CALLOWED",
            )
        )


if __name__ == "__main__":
    unittest.main()

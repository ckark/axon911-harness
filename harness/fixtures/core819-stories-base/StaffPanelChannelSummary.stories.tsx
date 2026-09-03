import type { Meta, StoryObj } from "@storybook/react-vite";
import { Button, ButtonType, CoreText, TextType, Typography } from "@prepared/ui-core";

const meta: Meta = { title: "Core819 Evidence/StaffPanelChannelSummary" };
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Typography>
      <CoreText type={TextType.BodyBase} medium>
        Needs my decision
      </CoreText>
      <CoreText type={TextType.BodyBase}>
        Something is ready or the agent needs your answer.
      </CoreText>
      <Button type={ButtonType.Secondary}>
        Needs my decision delivery channels, In app, Slack
      </Button>
    </Typography>
  ),
};

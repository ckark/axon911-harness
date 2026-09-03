import type { Meta, StoryObj } from "@storybook/react-vite";
import { Callout, CalloutType, CoreText, Typography } from "@prepared/ui-core";

const meta: Meta = { title: "Core819 Evidence/ProtocolSourceBanner" };
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Callout
      type={CalloutType.Info}
      title="Protocol upload in progress"
      description={
        <Typography>
          <CoreText>Estimated time remaining: 5 minutes</CoreText>
        </Typography>
      }
    />
  ),
};

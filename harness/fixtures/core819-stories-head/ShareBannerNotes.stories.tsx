import type { Meta, StoryObj } from "@storybook/react-vite";
import { Callout, CalloutType, CoreText, Typography } from "@prepared/ui-core";

const meta: Meta = {
  title: "Core819 Evidence/ShareBannerNotes",
};

export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Callout
      type={CalloutType.Warning}
      title="Shared from Source PSAP"
      description={
        <Typography>
          <CoreText>Note from Source PSAP: Caller reports smoke on Oak Street</CoreText>
        </Typography>
      }
    />
  ),
};

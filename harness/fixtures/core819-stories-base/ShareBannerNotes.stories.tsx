import type { Meta, StoryObj } from "@storybook/react-vite";
import { Callout, CalloutType } from "@prepared/ui-core";

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
        <>
          <strong>Note from Source PSAP:</strong> Caller reports smoke on Oak Street
        </>
      }
    />
  ),
};

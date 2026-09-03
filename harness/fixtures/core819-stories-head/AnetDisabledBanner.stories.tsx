import type { Meta, StoryObj } from "@storybook/react-vite";
import { AlignItems, Button, ButtonType, Callout, CalloutType, FlexBox } from "@prepared/ui-core";

const meta: Meta = { title: "Core819 Evidence/AnetDisabledBanner" };
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <FlexBox alignItems={AlignItems.Center} gap={1}>
      <Callout
        type={CalloutType.Warning}
        title="Non-emergency triage is currently disabled."
      />
      <Button type={ButtonType.Link} href="/supervisor/nonemergency">
        Enable in settings
      </Button>
    </FlexBox>
  ),
};

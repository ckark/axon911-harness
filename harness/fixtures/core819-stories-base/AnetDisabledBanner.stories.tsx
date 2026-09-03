import type { Meta, StoryObj } from "@storybook/react-vite";
import {
  Button,
  ButtonType,
  Callout,
  CalloutType,
} from "@prepared/ui-core";

const meta: Meta = { title: "Core819 Evidence/AnetDisabledBanner" };
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Callout
      type={CalloutType.Warning}
      title={
        <span style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
          Non-emergency triage is currently disabled.
          <Button type={ButtonType.Link} href="/supervisor/nonemergency">
            Enable in settings
          </Button>
        </span>
      }
    />
  ),
};

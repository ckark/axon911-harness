import type { Meta, StoryObj } from "@storybook/react-vite";
import { Callout, CalloutType } from "@prepared/ui-core";

const meta: Meta = { title: "Core819 Evidence/AnalysisNotRunCallout" };
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Callout
      type={CalloutType.Info}
      title="Protocol upload in progress"
      description={<strong>Estimated time remaining: 5 minutes</strong>}
    />
  ),
};

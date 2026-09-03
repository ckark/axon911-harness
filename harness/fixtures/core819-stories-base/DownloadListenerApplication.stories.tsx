import type { Meta, StoryObj } from "@storybook/react-vite";
import { DownloadListenerApplication } from "~src/modules/manage-audio/AudioManagementPage/DownloadListenerApplication";

const meta: Meta<typeof DownloadListenerApplication> = {
  title: "Core819 Evidence/DownloadListenerApplication",
  component: DownloadListenerApplication,
};

export default meta;
type Story = StoryObj<typeof DownloadListenerApplication>;

export const Default: Story = {};

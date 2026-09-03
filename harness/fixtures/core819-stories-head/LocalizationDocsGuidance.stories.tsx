import type { Meta, StoryObj } from "@storybook/react-vite";
import { CoreText, TextType, Typography } from "@prepared/ui-core";

const meta: Meta = { title: "Core819 Evidence/LocalizationDocsGuidance" };
export default meta;
type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Typography>
      <CoreText type={TextType.HeadingMd}>Localization (i18n)</CoreText>
      <CoreText type={TextType.BodyBase}>
        The useTranslation hook provides a consistent API for handling translations, formatting dynamic
        content, and managing locale-sensitive data across the application.
      </CoreText>
      <CoreText type={TextType.HeadingSm}>LocalizedMessage branding</CoreText>
      <CoreText type={TextType.BodyBase}>
        @prepared/tool-localization exports a LocalizedMessage branded string type and
        brandLocalizedMessage() for values produced by formatters.
      </CoreText>
    </Typography>
  ),
};

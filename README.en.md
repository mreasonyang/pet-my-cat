[简体中文](README.md) | [日本語](README.ja.md) | English

# Pet My Cat (我家猫来客串)

A clear top-down, full-body photo of your cat can be turned directly into an interactive guest you can pet on the back and swish by the tail right in your browser. If you only have front, side, or curled-up everyday snapshots, you can optionally use an image tool to synthesize a top-down posture from your reference photos—or, if your photos must stay on your device and no local image generator is available, snap one top-down photo showing the back and tail to follow the pure real-photo cutout route. Your finished cat works inside your open [upstream site](https://pet-the-cat.pages.dev/) tab or as an offline personal webpage. Close the temporary view or refresh the upstream page anytime to return to the original site.

## Getting Started

1. **Install the skill folder**: Clone this repository, or download the latest release archive [`pet-my-cat.zip`](https://github.com/mreasonyang/pet-my-cat/releases/latest/download/pet-my-cat.zip), extract it, and ensure the complete folder is named `pet-my-cat` inside your project's `.agents/skills/` directory (or let your agent read `pet-my-cat/SKILL.md` directly after extracting). See the [Codex Skills documentation](https://developers.openai.com/codex/skills/) for details.
2. **Attach photos and invoke**: To preserve your cat's exact coat markings, start with a nearly vertical top-down photo showing the ears, full back, and tail from base to tip. Attach the best photo(s) you have and copy one of these one-line prompts to your agent:

   - **With a top-down photo**:
     > Use $pet-my-cat to temporarily add my cat photo to the cat-petting webpage and play in the current tab.

   - **With everyday photos (generate a top-down posture)**:
     > Use $pet-my-cat to temporarily add Mochi to the cat-petting webpage. Reference these two everyday photos to generate a top-down posture, keep the visible markings accurate, and approximate the unseen back pattern.

3. **Play in the current tab or offline**: The agent prepares a personal HTML file on your machine. When browser control is available, it can mount the session directly into your open upstream tab. To load the file manually, open the bundled [bookmarklet tool](assets/current-tab.html), follow the on-page steps to add the bookmarklet, and pick your personal HTML file from the upstream tab. You can also open the personal HTML directly in a desktop browser for offline play. Closing the temporary view restores the previously selected cat, and refreshing the upstream tab clears the temporary session.

## Local Edge Trimming

When your cat's fur is similar in color to a scratcher, mat, or floor, you might notice a small patch of background moving with the cat while petting. Simply tell the agent the exact spot—for example, *"there is still a small strip of cardboard scratcher along the upper back edge."* It will zoom in against the original photo, trim the leftover background along the fur tips, and rebuild your updated personal HTML.

## Language & UI Scope

The skill itself supports `zh-CN` (Simplified Chinese), `ja` (Japanese), and `en` (English):

- **Conversation & skill notices**: The agent responds in your conversation language. The build language setting (which controls the skill's own prompts/notices and the default fallback cat name—`我家的猫` / `うちの猫` / `My cat`—when no name is specified) honors your explicit request first, or else follows the conversation language. Any name provided by the cat's owner is used verbatim.
- **Bookmarklet wizard**: The [bookmarklet tool](assets/current-tab.html) and its overlay dialog automatically match your browser language and can be switched manually on the page. Choosing a personal HTML and bookmarklet language that match keeps the skill notices consistent.
- **Original Japanese game UI preserved**: The live [upstream site](https://pet-the-cat.pages.dev/) is maintained online by its original author. Both on the public site and in your local personal session, the upstream game's native controls—cat picker, body type, sound, keyboard shortcuts, and other game UI—remain in their original Japanese. This skill does not translate the upstream game controls.

## Local Processing, AI Privacy & License

- **Local assembly & on-demand AI consent**: Your personal webpage is assembled locally using Python 3, and the bundled photo slicing and trimming helper uses Pillow. Real-photo cutouts can be completed entirely on your machine. Only if you choose cloud-based image generation for viewpoint synthesis or partial inpainting will reference photos be sent to an external service—and the agent will name the specific cloud service and ask for your consent beforehand.
- **Local assets never uploaded to the upstream site**: Your cat photos, extracted layers, and generated personal HTML remain on your device and are never uploaded to the upstream site. Share the skill package publicly, while keeping each person's photos and personal HTML saved privately.
- **License & ownership**: The code and documentation in this skill package are licensed under the [MIT License](LICENSE). The [upstream site](https://pet-the-cat.pages.dev/) content, artwork, and audio belong to their original creator, and personal cat photos along with the derived personal cat assets belong to their respective owners.

Vision

Copy page

Claude's vision capabilities allow it to understand and analyze images, opening up exciting possibilities for multimodal interaction.
This guide describes how to work with images in Claude, including best practices, code examples, and limitations to keep in mind.

How to use vision
Use Claude’s vision capabilities through:

claude.ai. Upload an image like you would a file, or drag and drop an image directly into the chat window.
The Console Workbench. A button to add images appears at the top right of every User message block.
API request. See the examples in this guide.
Before you upload
Basics and limits
You can include multiple images in a single request: up to 20 for claude.ai, and up to 600 for API requests (100 for models with a 200k-token context window). Claude analyzes all provided images when formulating its response. This can be helpful for comparing or contrasting images.

If you submit an image larger than 8000x8000 px, it is rejected. If you submit more than 20 images in one API request, this limit is 2000x2000 px.

While the API supports up to 600 images per request, request size limits (32 MB for standard endpoints; lower on some third-party platforms) can be reached first. For many images, consider uploading with the Files API and referencing by file_id to keep request payloads small.

Even when using the Files API, requests with many large images can fail before reaching the 600-image count. Reduce image dimensions or file sizes (for example, by downsampling) before uploading (see Evaluate image size).
Evaluate image size
For optimal performance, resize images before uploading if they are too large. If your image's long edge is more than 1568 pixels, or your image is more than ~1,600 tokens, it is first scaled down, preserving aspect ratio, until it's within the size limits.

If your input image is too large and needs to be resized, it increases latency of time-to-first-token, with no benefit to output quality. Very small images under 200 pixels on any given edge may degrade output quality.

To improve time-to-first-token, consider resizing images to no more than 1.15 megapixels (and within 1568 pixels in both dimensions).
Here is a table of maximum image sizes accepted by the API that will not be resized for common aspect ratios. With Claude Sonnet 4.6, these images use approximately 1,600 tokens and around $4.80/1k images.

Aspect ratio	Image size
1:1	1092x1092 px
3:4	951x1268 px
2:3	896x1344 px
9:16	819x1456 px
1:2	784x1568 px
Calculate image costs
Each image you include in a request to Claude counts towards your token usage. To calculate the approximate cost, multiply the approximate number of image tokens by the per-token price of the model you’re using.

If your image does not need to be resized, you can estimate the number of tokens used through this algorithm: tokens = (width px * height px)/750

Here are examples of approximate tokenization and costs for different image sizes within the API's size constraints based on Claude Sonnet 4.6 per-token price of $3 per million input tokens:

Image size	# of Tokens	Cost / image	Cost / 1k images
200x200 px(0.04 megapixels)	~54	~$0.00016	~$0.16
1000x1000 px(1 megapixel)	~1334	~$0.004	~$4.00
1092x1092 px(1.19 megapixels)	~1590	~$0.0048	~$4.80
Ensuring image quality
When providing images to Claude, keep the following in mind for best results:

Image format: Use a supported image format: JPEG, PNG, GIF, or WebP.
Image clarity: Ensure images are clear and not too blurry or pixelated.
Text: If the image contains important text, make sure it’s legible and not too small. Avoid cropping out key visual context just to enlarge the text.
Prompt examples
Many of the prompting techniques that work well for text-based interactions with Claude can also be applied to image-based prompts.

These examples demonstrate best practice prompt structures involving images.

Just as placing long documents before your query improves results in text prompts, Claude works best when images come before text. Images placed after text or interpolated with text still perform well, but if your use case allows it, prefer an image-then-text structure.
About the prompt examples
The following examples demonstrate how to use Claude's vision capabilities using various programming languages and approaches. You can provide images to Claude in three ways:

As a base64-encoded image in image content blocks
As a URL reference to an image hosted online
Using the Files API (upload once, use multiple times)
The base64 example prompts use these variables:

Shell
    # For URL-based images, you can use the URL directly in your JSON request

    # For base64-encoded images, you need to first encode the image
    # Example of how to encode an image to base64 in bash:
    BASE64_IMAGE_DATA=$(curl -s "https://upload.wikimedia.org/wikipedia/commons/a/a7/Camponotus_flavomarginatus_ant.jpg" | base64)

    # The encoded data can now be used in your API calls
Below are examples of how to include images in a Messages API request using base64-encoded images and URL references:

Base64-encoded image example
Shell
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d @- <<EOF
{
  "model": "claude-opus-4-6",
  "max_tokens": 1024,
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "image",
          "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": "$BASE64_IMAGE_DATA"
          }
        },
        {
          "type": "text",
          "text": "Describe this image."
        }
      ]
    }
  ]
}

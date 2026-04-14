EOF
URL-based image example
Shell
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "image",
            "source": {
              "type": "url",
              "url": "https://upload.wikimedia.org/wikipedia/commons/a/a7/Camponotus_flavomarginatus_ant.jpg"
            }
          },
          {
            "type": "text",
            "text": "Describe this image."
          }
        ]
      }
    ]
  }'
Files API image example
For images you'll use repeatedly or when you want to avoid encoding overhead, use the Files API. Upload the image once, then reference the returned file_id in subsequent messages instead of resending base64 data.

In multi-turn conversations and agentic workflows, each request resends the full conversation history. If images are base64-encoded, the full image bytes are included in the payload on every turn, which can significantly increase request size and latency as the conversation grows. Uploading images to the Files API and referencing them by file_id keeps request payloads small regardless of how many images accumulate in the conversation history.
Shell
# First, upload your image to the Files API
curl -X POST https://api.anthropic.com/v1/files \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: files-api-2025-04-14" \
  -F "file=@image.jpg"

# Then use the returned file_id in your message
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: files-api-2025-04-14" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 1024,
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "image",
            "source": {
              "type": "file",
              "file_id": "file_abc123"
            }
          },
          {
            "type": "text",
            "text": "Describe this image."
          }
        ]
      }
    ]
  }'
See Messages API examples for more example code and parameter details.


Example: One image

Example: Multiple images

Example: Multiple images with a system prompt

Example: Four images across two conversation turns
Limitations
While Claude's image understanding capabilities are cutting-edge, there are some limitations to be aware of:

People identification: Claude cannot be used to name people in images and refuses to do so.
Accuracy: Claude may hallucinate or make mistakes when interpreting low-quality, rotated, or very small images under 200 pixels.
Spatial reasoning: Claude's spatial reasoning abilities are limited. It may struggle with tasks requiring precise localization or layouts, like reading an analog clock face or describing exact positions of chess pieces.
Counting: Claude can give approximate counts of objects in an image but may not always be precisely accurate, especially with large numbers of small objects.
AI generated images: Claude does not know if an image is AI-generated and may be incorrect if asked. Do not rely on it to detect fake or synthetic images.
Inappropriate content: Claude does not process inappropriate or explicit images that violate the Acceptable Use Policy.
Healthcare applications: While Claude can analyze general medical images, it is not designed to interpret complex diagnostic scans such as CTs or MRIs. Claude's outputs should not be considered a substitute for professional medical advice or diagnosis.
Always carefully review and verify Claude's image interpretations, especially for high-stakes use cases. Do not use Claude for tasks requiring perfect precision or sensitive image analysis without human oversight.

FAQ

What image file types does Claude support?

Can Claude read image URLs?

Is there a limit to the image file size I can upload?

How many images can I include in one request?

Does Claude read image metadata?

Can I delete images I've uploaded?

Where can I find details on data privacy for image uploads?

What if Claude's image interpretation seems wrong?

Can Claude generate or edit images?
Dive deeper into vision
Ready to start building with images using Claude? Here are a few helpful resources:

Multimodal cookbook: This cookbook has tips on getting started with images and best practice techniques to ensure the highest quality performance with images. See how you can effectively prompt Claude with images to carry out tasks such as interpreting and analyzing charts or extracting content from forms.
API reference: Documentation for the Messages API, including example API calls involving images.
If you have any other questions, reach out to the support team. You can also join the developer community to connect with other creators and get help from Anthropic experts.
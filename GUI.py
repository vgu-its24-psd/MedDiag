import tkinter as tk
from tkinter import filedialog
import requests, base64

NGROK_URL = "https://unstiffened-eulalia-unmorphologically.ngrok-free.dev/diagnose"  # from Colab output

selected_images = []

def add_image():
    filepaths = filedialog.askopenfilenames(filetypes=[("Images","*.png;*.jpg;*.jpeg")])
    for f in filepaths:
        selected_images.append(f)
    img_label.config(text="\n".join(selected_images))

def send_case():
    prompt = text_box.get("1.0", tk.END).strip()
    images_b64 = []
    for path in selected_images:
        with open(path, "rb") as f:
            images_b64.append(base64.b64encode(f.read()).decode("utf-8"))
    payload = {"user_input": prompt, "images": images_b64}
    r = requests.post(NGROK_URL, json=payload)
    data = r.json()
    output.config(text=data.get("result", data.get("error", "Unknown error")))

root = tk.Tk()
root.title("Dengue Diagnostic GUI")

# Multi-line, resizable text box
text_box = tk.Text(root, wrap="word", height=10, width=60)
text_box.pack(expand=True, fill="both")

btn_img = tk.Button(root, text="Add Image", command=add_image)
btn_img.pack()

img_label = tk.Label(root, text="No image selected", anchor="w", justify="left")
img_label.pack(fill="x")

btn_run = tk.Button(root, text="Run Diagnosis", command=send_case)
btn_run.pack()

output = tk.Label(root, text="", wraplength=500, justify="left")
output.pack(fill="both", expand=True)

root.mainloop()

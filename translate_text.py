import pandas as pd
from googletrans import Translator

csv_fn = "coorteeqsrafva.csv"

# Load the CSV file
df = pd.read_csv(csv_fn, sep=";", header=0, index_col=0, encoding="utf-8")

# Create a translator object
translator = Translator()

# Define a function to translate a text string
def translate_text(text):
    try:
        translation = translator.translate(text, src="de", dest="en")
        return translation.text
    except:
        # If there's an error with translation, return the original text
        return text


# Apply the translation function to the "report" column of the DataFrame
df["report"] = df["report"].apply(translate_text)

# Save the updated DataFrame to a new CSV file
out_fn = csv_fn[:-4] + "_en.csv"
df.to_csv(out_fn, sep=";", index=False)

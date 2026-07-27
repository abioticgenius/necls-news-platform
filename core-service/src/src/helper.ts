

export const denormalizeString = (str: string): string => {
  return str
    .split("_")
    .map(word => {
      if (word === "and") return "&"; // restore semantic symbol
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
};

export const normalizeString = (str: string): string => {
  return str
    .trim()
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[\/]/g, " ")
    .replace(/[^a-z0-9\s]/g, "")
    .replace(/\s+/g, "_");
};
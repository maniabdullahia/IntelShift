def extract_open_graph(soup):
    data = {}

    for tag in soup.find_all("meta"):
        prop = tag.get("property") or tag.get("name")
        content = tag.get("content")

        if prop and content and prop.startswith("og:"):
            data[prop.replace("og:", "")] = content

    return data

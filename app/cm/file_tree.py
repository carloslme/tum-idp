import os

def generate_file_tree(root_path: str, max_depth: int = None, show_files: bool = True, prefix: str = "") -> str:
    """
    Generate a file tree in string format. 
    This can help LLM to understand the structure of repo, which decrease the potential of lowering LLM's attention on other important information.
    This function can be used on ReadME.
    :param root_path: selected root path of the repo
    # TODO: Open a window to let user select root path. (Must)
    :param max_depth: Max depth of the file tree. Control the size of file tree.
    # TODO: Automatically generate the max depth of file tree. (Should)
    :param show_files: Only show folders' name or detailed files' name.
    :param prefix: a parameter to bring blank space for sub tree.
    :return: a file tree in string format.
    """
    # TODO more logic to prevent buggy parameter
    if max_depth is not None and max_depth < 1:
        return ""

    tree = []
    entries = sorted(
        [entry for entry in os.listdir(root_path) if not entry.startswith(".")]
    )
    for i, entry in enumerate(entries):
        entry_path = os.path.join(root_path, entry)
        connector = "└── " if i == len(entries) - 1 else "├── "
        
        # if folder or show_files is allowed, add to tree
        if os.path.isdir(entry_path) or show_files:
            tree.append(f"{prefix}{connector}{entry}")
        
        # recursive add sub tree
        if os.path.isdir(entry_path):
            subtree_prefix = f"{prefix}{'    ' if i == len(entries) - 1 else '│   '}"
            subtree = generate_file_tree(
                entry_path,
                max_depth=None if max_depth is None else max_depth - 1,
                show_files=show_files,
                prefix=subtree_prefix
            )
            if subtree:
                tree.append(subtree)

    return "\n".join(tree)

# # test
# if __name__ == "__main__":
#     root = "D:\TUM_Workplace\dhmin\dhmin"
#     max_depth = 4 
#     show_files = True 
#     tree = generate_file_tree(root, max_depth=max_depth, show_files=show_files)
#     print(tree)

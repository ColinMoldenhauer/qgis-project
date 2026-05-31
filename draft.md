
```python
proj = Project()


group1 = Group("2013-01-01", "water")
proj.add_group(group1)

l1 = Layer(
    "file1.tif",
    name="layer1",  # default is basename without extension
    group=["2013-01-01", "water"],
    group=group1,
)
l1.set_name("layer1")
l1.set_group("2013-01-01", "water")

s1 = Style(
    colormap="viridis",
    vmin=0.,
    vmax=1.,
    visible=False,  # TODO how to?
)
l1.set_style(s1)
l1.set_visibility(True)


l2 = Layer("file2.tif")
s2 = Style(
    vmin="auto",
    vmax="auto",
)
l2.set_style(s2)

proj.add_layer(l1)
proj.add_layer(
    l2,
    mode_existing=["overwrite", "ignore"][0],
    )

proj.save("my_proj.qgz")
proj.open()
```

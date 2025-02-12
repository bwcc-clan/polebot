from lagom import Container


class ContainerProvider:
    def __init__(self, container: Container) -> None:
        self.container = container

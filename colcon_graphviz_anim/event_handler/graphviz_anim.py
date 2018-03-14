# Copyright 2016-2018 Dirk Thomas
# Licensed under the Apache License, Version 2.0

import atexit
import os

from colcon_core.environment_variable import EnvironmentVariable
from colcon_core.event.job import JobEnded
from colcon_core.event.job import JobQueued
from colcon_core.event.job import JobStarted
from colcon_core.event.output import StderrLine
from colcon_core.event_handler import EventHandlerExtensionPoint
from colcon_core.plugin_system import satisfies_version
from gvanim import Animation
from gvanim import gif
from gvanim import render

"""Environment variable to generate an animation of the progress"""
ANIMATION_PROGRESS_ENVIRONMENT_VARIABLE = EnvironmentVariable(
    'COLCON_ANIMATION_PROGRESS',
    'Flag to generate an animation of the progress')


class GraphvizAnimEventHandler(EventHandlerExtensionPoint):
    """
    Generate a .gif of the task progress.

    The animation file `graphviz_anim_build.gif` is created in the current
    working directory.

    The extension handles events of the following types:
    - :py:class:`colcon_core.event.job.JobQueued`
    - :py:class:`colcon_core.event.job.JobStarted`
    - :py:class:`colcon_core.event.job.JobEnded`
    - :py:class:`colcon_core.event.output.StderrLine`
    """

    # the priority should be lower than all status and notification extensions
    # in order to not block them while generating the animation
    PRIORITY = 10

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            EventHandlerExtensionPoint.EXTENSION_POINT_VERSION, '^1.0')
        self._animation = Animation()
        self._node_dependencies = {}
        self._any_started = False
        self._node_colors = {}
        self._has_errors = set()
        self._enabled = os.environ.get(
            ANIMATION_PROGRESS_ENVIRONMENT_VARIABLE.name, False)

        # register exit handle to ensure the last status line is cleared
        atexit.register(self._finish)

    def __call__(self, event):  # noqa: D102
        # skip any processing if not explicitly enabled
        if not self._enabled:
            return

        data = event[0]

        if isinstance(data, JobQueued):
            self._animation.add_node(data.identifier)
            self._node_dependencies[data.identifier] = set(
                data.dependencies.keys())

        elif isinstance(data, JobStarted):
            if not self._any_started:
                # add nodes with dependency edges
                # while ignoring unknown dependencies
                for node, deps in self._node_dependencies.items():
                    for dep in deps:
                        if dep not in self._node_dependencies:
                            continue
                        self._animation.add_edge(dep, node)
                self._any_started = True
            self._animation.next_step()
            self._node_colors[data.identifier] = 'blue'
            self._apply_highlights()

        elif isinstance(data, JobEnded):
            self._animation.next_step()
            job = event[1]
            color = 'green'
            if data.rc:
                color = 'red'
            elif job in self._has_errors:
                color = 'orange'
            self._node_colors[data.identifier] = color
            self._apply_highlights()

        elif isinstance(data, StderrLine):
            job = event[1]
            self._has_errors.add(job)

    def _apply_highlights(self):
        for node, color in self._node_colors.items():
            self._animation.highlight_node(node, color=color)

    def _finish(self):
        if not self._any_started:
            return
        graphs = self._animation.graphs()
        files = render(graphs, 'graphviz_anim_build', fmt='gif', size=1920)
        gif(files, 'graphviz_anim_build', delay=50)

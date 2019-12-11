=====================
Contributing to Merou
=====================

Current State
=============

Merou is not currently in wonderful shape for use outside Dropbox.  We
intend to improve that over time, but if you're investigating it for use
now, be aware that we're not yet making releases, are doing substantial
refactorings, may drop features, may change database schemas, and will
probably rename the project again.  You should therefore have a high
tolerance for change if you use it today.

Python 3.7 or later is required.

Merou used to be called Grouper and is still called Grouper internally at
Dropbox.  We renamed the public project to avoid `a namespace conflict
<https://github.com/Internet2/grouper>`_, but it's still called Grouper in
the code, comments, module namespace, and so forth.  We've not yet fixed
this because we've not yet settled on a final name.

This code is in the middle of a very substantial refactoring.  While that
refactoring is in progress, expect considerable amounts of code
duplication and other oddities, workarounds for legacy behavior, and
suboptimal code.  Most of this file describes the intended new
architecture and the steps to take to refactor part of the old code to the
new architecture.  We expect to do this refactoring as we touch pieces of
the code for bug fixes or feature additions, and expect to do it slowly
over a fairly extended period of time.

Tools
=====

Merou development uses the following static analysis and style tools:

- `black <https://github.com/ambv/black>`_
- `flake8 <http://flake8.pycqa.org/en/latest/>`_ with the
  `flake8-import-order plugin
  <https://github.com/PyCQA/flake8-import-order>`_
- `mypy <http://mypy-lang.org/>`_

All of these tools can be run from the top of the source base on all files
with no further configuration than that included in the repository,
provided that you use the versions defined in `requirements-dev.txt`.

All new code must produce no output with all three tools.

Continuous integration testing is done via `Travis-CI
<https://travis-ci.org/dropbox/merou/>`_.  Tests are run with both SQLite
(the default for local tests) and MySQL (whatever version is provided by
the default Travis-CI environment).  All tests must pass before new code
is merged.

Architecture
============

Below is a somewhat verbose introduction to the Merou architecture, aimed
at people who haven't seen hexagonal architecture before or who are not
used to using abstract base classes and strongly typed objects in Python.
For quicker and more checklist-based instructions on how to write new code
or refactor legacy code, see `Checklists`_.

New Merou code uses `hexagonal architecture
<https://fideloper.com/hexagonal-architecture>`_, sometimes also known as
"ports and adapters," and makes heavy use of abstract base classes to
define interfaces and mypy types for static analysis.  Python programmers
may find this style a little odd at first, since it's more common in other
programming languages with a stronger type system.

Hexagonal architecture is designed in layers, with the core business logic
in the center and the frameworks used for the user interface or the
database storage in the outer ring.  Communication from the outer layers
to the inner layer happens via defined interfaces that may have multiple
implementations.  This decouples decisions about interactions with the
outside world from the core business logic, allowing the same logic to be
reused with multiple user interfaces and database backends.

UI to Use Case
--------------

In Merou, there are three separate UIs:

- API server: uses Tornado web handlers, returns JSON
- Frontend server: uses Tornado web handlers with Jinja2 and WTForms,
  returns HTML for a browser
- The `grouper-ctl` command-line tool: takes command line arguments and
  reports the results with `print` or Python `logging`

There may be additional UIs in the future.  All of these UIs gather data
for the request from a user and then instantiate and call a *use case*.
Use cases (modules in `grouper.usecases`) implement the core business
logic and return the results via callbacks to the UI.

The use case returns results to the UI via callbacks, **not** return
values.  This will seem a little strange at first, but it avoids having to
declare complex error return types in Python (which Python does not handle
well).  When constructing a use case, the UI must provide a UI class that
implements the interface defined by that use case.  For example, the
disable permission use case defines this UI at the time this
documentation was written:

.. code:: python

    disabled_permission(self, name)
    disable_permission_failed_because_not_found(self, name)
    disable_permission_failed_because_permission_denied(self, name)
    disable_permission_failed_because_system_permission(self, name)

The first method is called on success, and the others are called for
various possible errors.  None of these callbacks are expected to return a
value.  Every use case should define an associated UI as an abstract base
class.

The call in the request handler on the UI side looks like:

.. code:: python

    usecase = usecase_factory.create_disable_permission_usecase(user, self)
    usecase.disable_permission(name)

This does not return a value.  Instead, the handler chains a call to the
use case, which then chains a call to one of the callbacks depending on
the result of the use case.  The callback in the UI is then responsible
for returning the results to the user.  All of these calls return `None`.
(Note that this requires a UI framework, like Tornado, that can return
results to a user without relying on method return values.)

If the use case needs to pass more complex data back to the UI, such as
lists of objects, that data is represented by a data transfer object
defined in `grouper.entities`.  These should be frozen dataclass objects.
Always use data transfer objects like this, rather than objects that are
artifacts of the underlying repository or have any behavior attached (in
other words, don't return SQLAlchemy models).

For paginated lists of objects, define an `Enum` to represent the possible
sort keys and then use the generic types defined in
`grouper.entities.pagination`.  The UI passes in a `Pagination` object as
one of the arguments to the use case, and the use case passes a
`PaginatedList` object as an argument to the success callback.

Use Case to Service
-------------------

Use cases themselves make decisions but do not change or query data
stores.  The mechanics of the requested operation is done via services
and, underneath the services, repositories.

The UI to use case call has a natural dependency direction: the UI depends
on the use case and implements the use case's UI interface.  The use case
to service call would naturally produce a dependency on the service from
the use case.  But the goal of this architecture is to isolate the use
case from the surrounding layers and ensure it doesn't depend on any given
implementation.  The natural dependency direction is therefore inverted
via dependency injection: when a use case is created, the services it
needs are provided as arguments to its constructor.

Every service a use case needs has a corresponding interface defined in
`grouper.usecases.interfaces`.  Often there is only one implementation of
that interface.  By convention, the single implementation is called
`FooService` and the interface `FooInterface`.

Use cases should make all *decisions*, including authorization, policy,
and enforcing invariants such as "you cannot disable a system permission."
Services should do all *work*, such as changing stored data, gathering
data and returning it as data transfer objects, and so forth.  (Some of
this work is delegated to underlying repository objects as described
later.)  A call to a service should only fail if the action requested is
impossible (retrieving a non-existent object, for instance).  All policy
decisions are made by the use case.

If the use case involves changing data in a persistent store, the use case
is responsible for managing the transaction.  This is because the work of
a use case may span multiple operations across multiple services, all of
which should be included in a single database transaction.  This is done
via `TransactionService` and a context manager.  Example:

.. code:: python

    with self.transaction_service.transaction():
        self.permission_service.disable_permission(name, authorization)

The underlying service, not the use case, is responsible for recording
changes in the audit log.

Note the `authorization` parameter in the above example.  All service
methods that make changes or display private data should require an
`authorization` parameter of type `Authorization` (defined in
`grouper.usecases.authorization`).  This just wraps the name of the user
making the change, but the explicit wrapping in a type allows
type-checking to verify that the use case made an intentional
authorization decision before calling the service.  Treat this as a
reminder to consider authorization policy (which must be enforced by the
use case) for actions that may require it.

Service to Repository
---------------------

The service is still not the component that makes changes directly in the
database.  It defers this work to a repository.  As with use cases,
services are created via dependency injection and passed the repositories
they use as arguments to their constructor.

The purpose of the repository layer is to isolate service logic from the
underlying database implementation.  The details of how data is stored and
retrieved should be isolated to the repository layer and not leak to the
service layer.  For example, the repository layer is responsible for
converting SQLAlchemy models to data transfer objects before returning
them to the service layer.

Repositories will generally correspond directly to types of objects stored
in the database.  For example, Merou has a permission repository,
representing a permission that can be granted, and a separate permission
grant repository representing those grants.  Services should represent a
higher-level view of the conceptual data model: a user service, a group
service, or a permission service.  Services may call each other; for
instance, the audit log service provides methods for logging each type of
recordable action, and then calls an audit repository to do the work of
storing that entry in the database.

In many cases, the service will be a thin pass-through method that just
calls a method on a repository.  This is fine.  It still achieves its goal
of isolating the service implementation from the database details.

Repositories
------------

The primary responsibility of a repository is to translate an action or
query on a data store, expressed as a method call, into operations on the
underlying data store.  Merou currently has two major classes of
repositories: graph and SQL.  Graph repositories normally wrap a SQL
repository, delegate write operations to the SQL repository, and answer
read-only questions from the graph.  SQL repositories perform all actions
with SQLAlchemy.

Any objects used by the underlying storage, such as graph data structures
or SQLAlchemy models, should not be exposed outside the repository layer.
All objects should be returned as data transfer objects defined under
`grouper.entities`.

The repository is doing its job properly if the underlying storage could
be replaced with a non-SQL data store and the API between the service and
the repository layers would not need to change.

What Goes Where?
----------------

Deciding what goes into the use case, the service, or the repository is
more art than science, and it's not that important to get it exactly right
every time.  Just keep the following guidelines in mind:

1. Use cases only call services.  Services only call repositories.
   Neither of those layers embed knowledge of the specific database
   implementation.  (There is currently an exception for the transaction
   service.)
2. Use cases make all *decisions*, including authorization and invariant
   enforcement, and then call a service to do the work.
3. Use cases are responsible for managing the transaction (opening and
   closing it) using the transaction service as a context manager.
4. Services coordinate between multiple repositories as needed, and are
   responsible for audit logging on changes.

Factories
---------

Since Merou uses dependency injection to construct use cases, services,
and repositories, constructing a new one requires a few lines to build its
dependencies first.  Merou encapsulates this code in factories so that it
doesn't have to be repeated in each UI and test case.

There is one factory (defined in the `factory.py` file in the
corresponding directory) for each of use cases, services, and
repositories.  The factory provides methods to create the objects in that
layer.  Whenever adding a new use case, service, or repository, also add a
method to the corresponding factory to create that object with all of its
dependencies.

The factory objects themselves also use dependency injection.  Each UI
provides a pre-constructed use case factory to its handlers, created as
part of initialization of the UI.  For tests, repository, service, and use
case factories are provided as attributes on the `SetupTest` object.

Templates
---------

There is a new mechanism for wrapping templates for the frontend (the `fe`
directory) in `grouper.fe.templates`.  Each template has a corresponding
dataclass class in that module that defines the variables required by that
template.  The call mechanism inside frontends then looks like:

.. code:: python

    template = SomeTemplate(variable=value, other=value)
    self.render_template_class(template)

This provides type checking for templates, ensuring that all the required
variables are passed in and are of the correct type.

Using this mechanism for all new templates is strongly encouraged, and
existing templates should be converted to this mechanism as they are
modified.  The code inside the frontend handlers is much cleaner and type
checking will catch bugs.

Testing
-------

Most testing, including exercising the failures, can be done at the use
case level using a mock UI.  Often, a `MagicMock` object is sufficient;
sometimes it will be easier to define a class that implements the UI to
make comparing returned data against expected data easier.

The `setup` fixture provides a `SetupTest` object, which provides a test
database session, methods to quickly assemble a test environment, and
factories for various Merou objects.  With it, you can create users,
groups, permissions, and assemble them.  Add more methods to that class if
you have more common setup patterns to automate.  All test setup should be
done inside a transaction using code like:

.. code:: python

    with setup.transaction():
        setup.create_user("gary@a.co")
        # ...

The `itests` directory contains integration tests that start a full API or
frontend server.  The frontend integration tests use Selenium to interact
with web pages; the API integration tests use groupy (the Merou client).
The frontend integration tests require that you specify a user, and all
requests to the frontend server will be authenticated as that user.
(Don't forget to create the user in the database first.)

As a general rule of thumb, the business logic should be thoroughly
tested, including error cases, by tests in `tests/usecases` that operate
directly on the use case, since this is much faster.  The slower
integration tests can then focus on UI concerns and success cases and
don't need to exercise all the errors unless there are regressions or
complex UI behavior.

`grouper-ctl` actions are tested via tests in `tests/ctl`.
`tests.ctl_util` provides a utility function to make running `grouper-ctl`
with a specific command line easier.

Avoid using the other fixtures defined in `tests.fixtures` and
`itests.fixtures`.  These are from the legacy tests, have various issues,
are slow to initialize and somewhat opaque, and will be retired
eventually.

Examples
--------

For a fully-worked example of a view action, see list permissions:

- `grouper.usecases.list_permissions`
- `grouper.services.permission` to retrieve the permissions
- `grouper.services.user` to check whether a user can create permissions
- `grouper.repositories.permission` to retrieve the permissions
- `grouper.fe.handlers.permissions_view`
- `grouper.api.handlers.Permissions`
- `tests.usecases.list_permissions_test`
- `itests.api.permissions_test`
- `itests.fe.permissions_test`

For a fully-worked example of a modification action, see disable
permission:

- `grouper.usecases.disable_permission`
- `grouper.services.permission`
- `grouper.services.user` to check authorization
- `grouper.repositories.permission`
- `grouper.ctl.permission`
- `grouper.fe.handlers.permission_disable`
- `tests.usecases.disable_permission_test`
- `tests.ctl.permission_test`
- `itests.fe.permission_view_test`

Checklists
==========

These are more linear than an actual development process, which will
frequently involve revisiting previous steps as you uncover new
complexity, but provide a shorter process outline.

New View Use Case
-----------------

#. If this is a new type of object, add a new data transfer object to
   `grouper.entities` that encapsulates the data that will be needed by
   the UI.
#. Write a test for the new use case in `tests.usecases`.  Cover the
   success and failures that you anticipate.  View use cases often don't
   have failures (you don't need to handle or test infrastructure failures
   such as inability to contact the database), but may if data is private
   and requires special permissions to view.
#. Write a new use case class in `grouper.usecases`.  This should define a
   use case class that contains the business logic, and an abstract base
   class for the UI callbacks.  There should be a callback for the success
   case and zero or more callbacks for error cases.  Often the use case
   class will have only a constructor and one method, but sometimes
   multiple use cases that can use the same UI can be provided by the same
   class with multiple methods.
#. If this use case returns a paginated list, define an enum for the sort
   keys and use the generic types in `grouper.entities.pagination`.
#. Add a factory method for the new use case to
   `grouper.usecases.factory`.
#. Add the additional service methods required to implement the use case
   to appropriate service interfaces in `grouper.usecases.interfaces`.
#. Implement those interfaces in the corresponding services.  This will
   generally involve one or more calls to repositories that return data
   transfer objects.
#. Add any new repository methods you need to the corresponding
   repositories.  If this use case involves data for which a repository
   has not already been written, write a new one, and consider whether
   there should be only a SQL repository or whether there should be both a
   graph repository and a SQL repository implementing the same interface.
   The graph repository, if needed, normally will embed a SQL repository
   and delegate write operations to it.
#. If separate graph and SQL repositories made sense, add an interface for
   the common API they implement to `grouper.repositories.interfaces`.
#. Check that the use case tests now pass.
#. Implement each UI and its corresponding test case.  Many use cases will
   only make sense in one or two of these UIs.

   #. Frontend UI invovles a handler in `grouper.fe.handlers`, possibly a
      route, possibly a new template and wrapper dataclass in
      `grouper.fe.templates`, and an integration test in `itests.fe`
      (which may require defining new pages in `itests.pages`).
   #. API UI involves a handler in `grouper.api.handlers` and an
      integration test in `itests.api`.
   #. `grouper-ctl` UI involves a new class in `grouper.ctl` and a test in
      `tests.ctl`.

New Modify Use Case
-------------------

#. If this is a new type of object, add a new data transfer object to
   `grouper.entities` that encapsulates the data passed from the UI into
   the use case.
#. Write a test for the new use case in `tests.usecases`.  Cover the
   success and failures that you anticipate.  Common failures are due to
   authorization, missing objects, duplicate objects, and invariant
   enforcement (such as deleting system permissions).
#. Write a new use case class in `grouper.usecases`.  This should define a
   use case class that contains the business logic, and an abstract base
   class for the UI callbacks.  There should be a callback for the success
   case and zero or more callbacks for error cases.  Often the use case
   class will have only a constructor and one method, but sometimes
   multiple use cases that can use the same UI can be provided by the same
   class with multiple methods.
#. Surround the code that makes the change with a transaction created via
   the `transaction()` method on a transaction service.
#. Create and pass an `Authorization` object into the service that is
   making the change.
#. Add a factory method for the new use case to
   `grouper.usecases.factory`.
#. Add the additional service methods required to implement the use case
   to appropriate service interfaces in `grouper.usecases.interfaces`.
#. Implement those interfaces in the corresponding services.  This will
   generally involve one or more calls to repositories.  A service method
   that changes something should generally require an `Authorization`
   object as a parameter.
#. Log the change to the audit log using an instance of
   `AuditLogService`.  You may have to define and implement new methods on
   that service for new actions.  You may need to log the same action
   multiple times with different affected `on_*` objects.
#. Add any new repository methods you need to the corresponding
   repositories.  If this use case involves data for which a repository
   has not already been written, write a new one, and consider whether
   there should be only a SQL repository or whether there should be both a
   graph repository and a SQL repository implementing the same interface.
   The graph repository, if needed, normally will embed a SQL repository
   and delegate write operations to it.
#. If separate graph and SQL repositories made sense, add an interface for
   the common API they implement to `grouper.repositories.interfaces`.
#. Check that the use case tests now pass.
#. Implement each UI and its corresponding test case.  Strongly consider
   implementing all new write UIs in `grouper-ctl` as well as the
   frontend.  It's often faster to test and is convenient later for
   automation or operations.

   #. Frontend UI invovles a handler in `grouper.fe.handlers`, possibly a
      route, possibly a new template and wrapper dataclass in
      `grouper.fe.templates`, and an integration test in `itests.fe`
      (which may require defining new pages in `itests.pages`).
   #. `grouper-ctl` UI involves a new class in `grouper.ctl` and a test in
      `tests.ctl`.

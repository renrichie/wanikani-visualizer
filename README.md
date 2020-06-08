# WaniKani Visualizer
This is a work in progress.

## To-do List
### Database
- [ ] Rewrite SQL to be more efficient.
### Backend
- [ ] Replace remaining custom database client usage with SQLAlchemy equivalents.
- [ ] Use locks to prevent simultaneous runs.
- [ ] Use a queue for asynchronous support and better response time handling.
- [ ] Rate limit the whole application as per WaniKani guidelines.
- [ ] Add asymmetric encryption to handle API keys from frontend to backend.
- [ ] Add Dockerfiles for Postgres, Zookeeper, and the Python backend.
### Other
- [ ] Add unit tests and integration tests
- [ ] Add documentation that explains what the program does and how.

### Nice to Have
- [ ] Split main entry point into multiple getters for populating the UI.
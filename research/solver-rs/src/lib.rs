//! Library face of the solver, so `tests/fixture.rs` can exercise
//! `bitstate`/`search`/`convert` directly against the same frozen fixture the
//! Python solver is checked against. `main.rs` is a thin CLI wrapper over this.

pub mod bitstate;
pub mod convert;
pub mod search;

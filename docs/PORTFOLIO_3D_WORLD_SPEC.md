# Kush Modi — Walkable 3D Portfolio World
## Strict Visual + Implementation Specification v0.1

> **Purpose:** Define the target website as a **walkable 3D environmental portfolio**, not a conventional scrolling portfolio. The visitor explores a small stylized world and discovers Kush's projects through physical locations, props, signs, terminals, and interactive objects.

> **Status:** Baseline specification. Once the current implementation is shared, use this document as the comparison target and produce a strict change/add/remove plan.

---

## 0. Core Product Definition

### The website is

**A small explorable 3D engineering outpost that doubles as a portfolio.**

The visitor should feel like they have entered a physical place that Kush built.

The world communicates the portfolio before the UI does.

### The website is NOT

- A normal landing page with a 3D background.
- A first-person shooter.
- A generic cyberpunk scene.
- A flat pixel-art image with clickable hotspots.
- A collection of floating project cards.
- A massive open-world game.
- A photorealistic architectural visualization.

### Primary design language

**3D environment + pixelated rendering + cinematic lighting + dense environmental storytelling.**

The uploaded reference image is the primary art-direction anchor:

![Reference design language](assets/reference-design-language.png)

---

# 1. Design Pillars

| Pillar | Requirement |
|---|---|
| Walkability | User physically moves through the environment |
| Discoverability | Projects are discovered by exploring |
| Environmental storytelling | Objects communicate what Kush builds |
| Pixel aesthetic | Geometry/materials/rendering have a deliberate pixelated treatment |
| Engineering identity | Robotics, electronics, aerospace, CAD, software and astronomy are visible |
| Density | Small details reward looking around |
| Performance | The world must remain lightweight enough for a portfolio site |
| Restraint | No unnecessary UI, effects, systems or game mechanics |

---

# 2. Reference World

The world should be a compact **engineering / research outpost** surrounded by natural terrain.

Conceptual structure:

![World navigation](assets/world-navigation.png)

### Primary locations

1. **START / PROFILE**
2. **ENGINEERING WORKSHOP**
3. **ROBOTICS FIELD**
4. **UAV / NETRA TEST FIELD**
5. **RESEARCH LAB**
6. **OBSERVATORY**

These are not separate web pages.

They are physical locations inside one world.

---

# 3. Environment Stack

The environment should be constructed in layers rather than as one giant model.

![Environment stack](assets/environment-stack.png)

## Layer 1 — World / Lighting

- Directional light
- Ambient/world light
- Local warm lights
- Cool emissive technology lights
- Optional fog
- Optional day/night state
- Contact shadows
- Controlled bloom
- No excessive post-processing

## Layer 2 — Terrain

Required:

- Main terrain
- Gentle hills
- Small slopes
- Dirt paths
- Clearings
- Rocks
- Terrain transitions
- Slight elevation changes

Avoid:

- Huge mountains
- Procedurally infinite terrain
- Empty flat ground
- Excessive terrain complexity

## Layer 3 — Ground Detail

Required asset families:

- Grass clumps
- Tall grass
- Dead grass
- Small flowers
- Pebbles
- Rocks
- Moss
- Dirt patches
- Fallen leaves
- Small puddles
- Tire/rover tracks
- Footpath wear

The same asset must have multiple rotations/scales/variants.

## Layer 4 — Vegetation

- Small bushes
- Medium bushes
- Trees
- Fallen branches
- Logs
- Sparse forest edges

Vegetation should frame important locations rather than hide them.

## Layer 5 — Story Props

Examples:

- Toolbox
- Multimeter
- Oscilloscope
- Soldering station
- PCB
- Breadboard
- ESP32/MCU-like boards
- Motors
- Servos
- LiPo battery
- Wires
- 3D printer
- Filament spools
- CAD printouts
- Antennas
- Sensors
- Drone parts

## Layer 6 — Hero Props

These are recognizable portfolio objects:

- Telescope
- Rover
- UAV
- Ground station
- Engineering workbench
- Research terminal
- Observatory

---

# 4. Pixelated 3D Rendering Rules

The target is **not low-poly for the sake of low-poly**.

The target is:

> **Readable 3D forms rendered with a deliberately limited/pixelated visual language.**

### Rendering direction

Recommended:

- Low-resolution render target or pixelation post-process
- Nearest-neighbour upscale
- Low-resolution texture maps where appropriate
- Limited material detail
- Strong silhouettes
- Controlled specular response
- Slight dithering where useful
- Hard/defined shadow boundaries
- Warm/cool lighting contrast

### Suggested starting render sizes

Desktop:

```text
Base render: 640 × 360
Display:     1280 × 720 or native viewport
Upscale:     nearest-neighbour
```

Do not lock these values until performance testing.

### Avoid

- Hyper-realistic PBR
- Film-grain overload
- Excessive chromatic aberration
- Heavy motion blur
- Excessive bloom
- Generic cyberpunk neon
- Plastic-looking grass
- Photorealistic trees
- Huge particle systems

---

# 5. Player / Camera

## Default

Third-person / over-the-shoulder or slightly elevated exploration camera.

The user should see:

- Character/avatar
- Ground
- Nearby objects
- Horizon
- Environment landmarks

### Alternative

A free-flying camera can be used for the first prototype, but the final experience should feel like **walking through a place**.

### Movement

Minimum:

- WASD / arrow movement
- Mouse camera control
- Sprint
- Collision
- Ground detection
- Basic gravity

Optional:

- Jump
- Crouch
- Controller support

Do not add game mechanics unless they improve portfolio exploration.

---

# 6. Navigation Philosophy

There should be a **clear main path**, but the visitor should be able to leave it.

Example:

```text
START
  |
  +---- ENGINEERING WORKSHOP
  |          |
  |          +---- ROBOTICS FIELD
  |
  +---- UAV TEST FIELD
  |          |
  |          +---- RESEARCH LAB
  |
  +---- OBSERVATORY
```

The world should naturally guide the visitor through:

**Profile → Engineering → Robotics → Aerospace → Research → Astronomy → Future**

This is a storytelling sequence, not a mandatory quest.

---

# 7. Location Specification

## 7.1 START — PROFILE CAMP

Purpose:

Introduce Kush.

Objects:

- Small camp/workbench
- Laptop
- Backpack
- Engineering notebook
- Small tools
- Sign/nameplate
- Personal workstation

Interaction:

Approaching the main workstation opens the profile/about interface.

Content:

- Name
- Short introduction
- Engineering focus
- Education
- Skills
- Current interests

Keep text short inside the world.

Detailed CV information can open in an HTML overlay.

---

# 8. ENGINEERING WORKSHOP

This is the primary technical location.

Visual identity:

- Wooden/metal workshop
- Workbench
- 3D printer
- Electronics bench
- Tools
- PCBs
- Motors
- Wires
- Shelves
- Prototype parts

Featured projects can include:

- AeroLink
- Enclosure / chamber project
- Embedded systems
- CAD/fabrication
- Telemetry systems

Interaction model:

```text
LOOK AT OBJECT
      ↓
INTERACTION PROMPT
      ↓
CLICK / ENTER
      ↓
PROJECT PANEL
      ↓
DESCRIPTION + MEDIA + LINKS
```

Do not teleport the user to another webpage unless explicitly requested.

---

# 9. ROBOTICS FIELD

Environment:

- Open grass
- Dirt testing path
- Small rocks
- Rover tracks
- Navigation markers
- Cones
- Telemetry mast
- Rover

Hero object:

**Darwin / rover representation**

Possible interactions:

- Inspect rover
- View robotics work
- Open project details
- Show competition/achievement information
- Display technical architecture

The rover should physically sit on the terrain and cast a shadow.

---

# 10. UAV / NETRA TEST FIELD

Environment:

- Larger clearing
- Drone landing pad
- Ground station
- Antenna mast
- Camera station
- Battery/charging station
- Small equipment crates

Hero object:

**UAV / drone**

Interaction:

Drone → Netra project.

Ground station → telemetry / architecture.

Antenna → communications/embedded systems.

The visitor should understand the project visually before opening the details.

---

# 11. RESEARCH LAB

Purpose:

Represent software/data/research work.

Visual elements:

- Small research cabin
- Screens
- Map
- Graphs
- Weather data
- Spatial visualization
- Computer
- Papers
- Data terminal

Potential project:

**Dengue forecasting / spatial-temporal modelling**

The environmental representation should remain visually understandable without exposing sensitive or overly academic detail.

---

# 12. OBSERVATORY

Purpose:

Represent:

- Astronomy
- Telescope work
- Astrophotography
- Go-To systems
- Space/astronomy interests

Objects:

- Telescope
- Tripod
- Camera
- Star tracker
- Observatory structure
- Control computer
- Star charts
- Equipment cases

The observatory should be one of the most visually recognizable locations.

---

# 13. Interactive Objects

Every major object should have an interaction state.

### Idle

Object exists naturally in the environment.

### Nearby

Small prompt:

```text
[ E ] INSPECT
```

### Focused

Object receives a subtle outline/highlight.

### Activated

Open a portfolio panel.

### Exit

```text
ESC / CLICK OUTSIDE
```

The interaction UI must not feel like a videogame HUD.

---

# 14. Portfolio Overlay

The 3D world remains visible behind the project information.

Recommended layout:

```text
┌─────────────────────────────────────────────┐
│ PROJECT                              [ X ] │
│                                             │
│  IMAGE / VIDEO      PROJECT TITLE           │
│                     ─────────────           │
│                     Short description       │
│                                             │
│                     TECHNOLOGY              │
│                     ESP32 · LoRa · IMU      │
│                                             │
│                     [ GitHub ] [ Demo ]     │
└─────────────────────────────────────────────┘
```

The overlay should feel like an extension of the environment, not a completely different website.

---

# 15. Asset Library

## Terrain

- `terrain_base`
- `terrain_slope`
- `terrain_dirt`
- `terrain_rock`
- `terrain_path`

## Grass

- `grass_short_01`
- `grass_short_02`
- `grass_tall_01`
- `grass_tall_02`
- `grass_dead_01`
- `grass_cluster_01`
- `grass_cluster_02`

## Rocks

- `rock_small_01`
- `rock_small_02`
- `rock_medium_01`
- `rock_medium_02`
- `rock_large_01`

## Vegetation

- `bush_01`
- `bush_02`
- `tree_small_01`
- `tree_small_02`
- `tree_medium_01`
- `fallen_branch_01`
- `log_01`

## Engineering props

- `workbench`
- `toolbox`
- `oscilloscope`
- `multimeter`
- `pcb`
- `breadboard`
- `motor`
- `servo`
- `battery`
- `wire_bundle`
- `3d_printer`
- `filament_spool`

## Robotics

- `rover`
- `rover_wheel`
- `lidar`
- `robot_arm`
- `telemetry_mast`

## Aerospace

- `uav`
- `uav_stand`
- `landing_pad`
- `ground_station`
- `antenna`
- `battery_station`

## Astronomy

- `telescope`
- `tripod`
- `camera`
- `star_tracker`
- `observatory`
- `astronomy_case`

---

# 16. Performance Requirements

This is a portfolio website, so performance is a first-class requirement.

### Required

- Lazy-load distant assets
- Use instancing for grass/rocks
- Use LODs
- Compress textures
- Avoid unnecessary 4K textures
- Keep collision meshes simple
- Avoid hundreds of unique materials
- Avoid heavy dynamic shadows everywhere
- Load locations progressively
- Dispose unused assets where applicable

### Target

Aim for:

```text
Desktop: 60 FPS
Laptop:  45–60 FPS
Mobile:  30+ FPS where practical
```

Do not sacrifice the entire environment for a theoretical benchmark.

---

# 17. Responsive / Device Strategy

## Desktop

Full experience.

Controls:

```text
W A S D       Move
Mouse         Look
Shift         Sprint
E             Interact
Esc           Close panel
```

## Mobile

Do not attempt to copy desktop controls.

Use:

- Virtual joystick
- Swipe camera
- Large interaction button
- Simplified graphics
- Reduced vegetation density
- Reduced shadow quality

Provide a lightweight mode.

---

# 18. Audio

Audio should be environmental and subtle.

Potential layers:

- Wind
- Grass
- Distant insects
- Workshop hum
- Electronics hum
- Servo movement
- Rover motor
- Drone startup
- Telescope motor

Do not autoplay loud music.

If music exists:

```text
Music: OFF by default
```

---

# 19. Day / Night System

Optional but strongly compatible with the concept.

### Day

- Green terrain
- Warm sunlight
- Workshop active
- Clear navigation

### Evening

- Orange horizon
- Workshop lights activate
- LEDs become visible

### Night

- Observatory becomes prominent
- Telescope illumination
- Cool ambient light
- Warm workshop windows
- Stars

The sky itself can remain a later phase.

**Current implementation priority: landscape and world first.**

---

# 20. UI Rules

### Keep UI minimal.

The environment does the storytelling.

UI should mainly provide:

- Location indicator
- Interaction prompt
- Project panel
- Controls/help
- Mute/audio
- Graphics quality

Avoid:

- Persistent navbar
- Giant hero text over the world
- Floating project cards everywhere
- Excessive HUD elements
- Giant skill bars

---

# 21. Technical Architecture

The implementation should be separated into:

```text
WORLD
 ├── Terrain
 ├── Vegetation
 ├── Props
 ├── Locations
 └── Lighting

PLAYER
 ├── Movement
 ├── Camera
 ├── Collision
 └── Interaction

PORTFOLIO
 ├── Projects
 ├── Profile
 ├── Experience
 ├── Skills
 └── Achievements

UI
 ├── InteractionPrompt
 ├── ProjectPanel
 ├── Settings
 └── LoadingScreen

ASSETS
 ├── Models
 ├── Textures
 ├── Audio
 └── VFX
```

The exact framework can be decided after reviewing the current implementation.

---

# 22. Data-Driven Projects

Project information should not be hardcoded into every 3D object.

Use a project definition:

```js
{
  id: "aerolink",
  title: "AeroLink",
  category: "UAV / Embedded",
  location: "uav-test-field",
  description: "...",
  technologies: [
    "ESP32",
    "IMU",
    "Telemetry",
    "WebSocket"
  ],
  links: {
    github: "...",
    demo: "..."
  },
  media: []
}
```

Then a physical object references:

```js
interactionTarget = "aerolink"
```

This allows the environment and portfolio content to evolve independently.

---

# 23. Loading / Entry Sequence

Recommended flow:

```text
LOADING
   ↓
WORLD INITIALIZES
   ↓
CAMERA FADES IN
   ↓
PLAYER LOOKS AROUND
   ↓
SMALL CONTROLS HINT
   ↓
FREE EXPLORATION
```

Do not begin with a giant conventional portfolio hero.

The world itself is the hero.

---

# 24. Environmental Storytelling Rules

Every visible technical object should answer at least one question:

### What does this say about Kush?

Examples:

**Telescope**

→ astronomy

**Rover**

→ robotics

**PCB**

→ embedded engineering

**3D printer**

→ fabrication

**Drone**

→ aerospace/UAV

**Research terminal**

→ data/research

**CAD drawing**

→ mechanical/design engineering

The environment should communicate the portfolio even before the visitor reads the text.

---

# 25. What Can Be Added Later

### Phase 2

- Day/night cycle
- Dynamic weather
- Ambient audio
- Animated props
- Birds/insects
- Moving rover
- Drone takeoff animation
- Telescope tracking animation
- Interactive screens

### Phase 3

- Save exploration state
- Interactive map
- Easter eggs
- Hidden projects
- Developer notes
- Timeline trail
- Achievement system

### Phase 4

- Multiplayer/shared world
- Procedural weather
- Seasonal environment
- Live project/repository data
- Dynamic GitHub activity representation

These are **not MVP requirements**.

---

# 26. Things That Should NOT Be Added Yet

Do not add:

- Multiplayer
- NPCs
- Combat
- Inventory
- Quests
- RPG systems
- Procedural infinite terrain
- Complex physics
- Massive open-world streaming
- Full VR
- Dozens of animations
- AI NPCs

They distract from the portfolio objective.

---

# 27. MVP Definition

The first working version is complete when:

- [ ] 3D world loads
- [ ] Player can walk
- [ ] Camera works
- [ ] Collision works
- [ ] Terrain exists
- [ ] Grass/rocks/vegetation exist
- [ ] Workshop exists
- [ ] Robotics area exists
- [ ] UAV area exists
- [ ] Observatory exists
- [ ] At least 3 interactive objects exist
- [ ] Interactions open portfolio panels
- [ ] World works without a traditional scrolling homepage
- [ ] Performance is acceptable
- [ ] Mobile fallback exists

---

# 28. Acceptance Test

A new visitor should be able to enter the website and, without reading documentation:

1. Understand that they are inside a world.
2. Figure out how to move.
3. Notice the engineering environment.
4. Find at least one obvious interactive object.
5. Open a project.
6. Close the project.
7. Continue exploring.
8. Discover another project through the environment.
9. Understand that different locations represent different parts of Kush's work.
10. Reach the observatory / final landmark.

If these ten things work, the core concept works.

---

# 29. Implementation Review Protocol

When the current implementation is supplied, compare it against this document.

For every existing component classify it as:

### KEEP

Already matches the target.

### MODIFY

Correct concept but wrong implementation/style.

### REPLACE

Fundamentally incompatible with the walkable-world direction.

### ADD

Required but currently missing.

### REMOVE

Adds complexity without improving the portfolio.

### DEFER

Useful later but not necessary for MVP.

For every change provide:

```text
Component
Current state
Problem
Required change
Why
Priority
Implementation notes
Acceptance criteria
```

Priorities:

```text
P0 = blocks the core experience
P1 = required for a convincing MVP
P2 = important polish
P3 = future enhancement
```

---

# 30. Final Art Direction

The finished world should feel like:

> **A young engineer's remote research outpost where robotics, aerospace, software, fabrication and astronomy have all converged into one physical place.**

The visitor should not feel like they are browsing a CV.

They should feel like they are **exploring the evidence of someone who builds things.**

---

## Reference Asset

Primary visual reference supplied for this specification:

`assets/reference-design-language.png`

Generated planning diagrams:

- `assets/world-navigation.png`
- `assets/environment-stack.png`

---

## Next Step

**Do not rebuild the website from this document yet.**

First provide the current implementation/screenshots/source/project structure.

Then create a second document:

`IMPLEMENTATION_GAP_ANALYSIS.md`

It should compare the existing website against this specification and explicitly list:

- what is already correct
- what should be changed
- what should be removed
- what should be added
- what should be redesigned
- asset requirements
- scene requirements
- interaction requirements
- performance problems
- UI problems
- camera/movement problems
- visual-style mismatches
- exact implementation order
- P0/P1/P2/P3 priorities
- final MVP acceptance checklist

**The existing implementation should be preserved where it already satisfies the target. Do not rewrite working systems merely for architectural purity.**

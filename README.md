# MythsAndLegends-Datapack

This is the official Datapack for Myths and Legends [Cobblemon Addon].

## Description

Welcome to the MythsAndLegends-Datapack repository. This repository hosts the official Datapack for the Myths and Legends Cobblemon Addon. The Datapack is needed for the Myths and Legends addon going forward from versions higher than 1.3 in order to add spawns that use the key items as a spawning condition. For more information, visit the addon pages on [Modrinth](https://modrinth.com/mod/cobblemon-myths-and-legends-addon) or [CurseForge](https://www.curseforge.com/minecraft/mc-mods/myths-and-legends-cobblemon-addon).

## Contributing

We encourage contributions to the MythsAndLegends-Datapack! You can contribute in several ways:

- **Fork the repository**: Create your own fork of this repository to modify and enhance the Datapack.
- **Create merge requests**: Submit your changes via merge requests for review and potential inclusion in the official Datapack. Please update the `SpawnListMythsAndLegends.xlsx` file if you want to merge something or if something is wrong.
- **Open issues**: Report bugs, suggest improvements, or share other feedback by opening an issue.

## Usage Guidelines

- **Modification**: Feel free to modify the pack to suit your needs.
- **Redistribution**: Do not redistribute this Datapack on sites like Modrinth, Curseforge, or similar platforms. This Datapack is intended for server use only.

## License

This project is licensed under the [Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License](https://creativecommons.org/licenses/by-nc-nd/4.0/).

## Contact

For further information, assistance, or any inquiries, please open an issue in this repository or join the Discord server: [https://discord.com/invite/EDesfBH2aS](https://discord.com/invite/EDesfBH2aS).

## Tutorial: Creating a Functioning Datapack

Follow these steps to create a functioning Datapack using 7-Zip or WinRAR.

### Step 1: Prepare Your Files

Ensure you have the following files and directories in your project:

- `data` directory: Contains your datapack data.
- `pack.mcmeta`: The metadata file for your datapack.
- `pack.png`: An optional image file for your datapack.

The structure should look like this:
```
[path-to-your-project]/mythsandlegends-datapack/data
[path-to-your-project]/mythsandlegends-datapack/pack.mcmeta
[path-to-your-project]/mythsandlegends-datapack/pack.png
```

### Step 2: Compress the Files

#### Using 7-Zip

1. Download and install [7-Zip](https://www.7-zip.org/).
2. Navigate to `[path-to-your-project]/mythsandlegends-datapack`.
3. Select the `data` folder, `pack.mcmeta`, and `pack.png`.
4. Right-click on the selected items and choose `7-Zip` > `Add to archive...`.
5. In the 7-Zip window, select `zip` as the archive format.
6. Name your archive (e.g., `mythsandlegends-datapack.zip`).
7. Click `OK` to create the archive.

#### Using WinRAR

1. Download and install [WinRAR](https://www.win-rar.com/).
2. Navigate to `[path-to-your-project]/mythsandlegends-datapack`.
3. Select the `data` folder, `pack.mcmeta`, and `pack.png`.
4. Right-click on the selected items and choose `Add to archive...`.
5. In the WinRAR window, select `ZIP` as the archive format.
6. Name your archive (e.g., `mythsandlegends-datapack.zip`).
7. Click `OK` to create the archive.

### Step 3: Install the Datapack

1. Open Minecraft and go to your world save directory. This can usually be found in `%appdata%/.minecraft/saves/[Your World Name]`.
2. Open the `datapacks` folder in your world save directory.
3. Copy the newly created `mythsandlegends-datapack.zip` into the `datapacks` folder.
4. Launch Minecraft and load your world.
5. Run the command `/reload` to activate the datapack.

Congratulations! You have successfully created and installed a functioning datapack.

Thank you for using and contributing to MythsAndLegends-Datapack!
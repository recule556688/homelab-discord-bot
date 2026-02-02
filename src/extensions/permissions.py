"""Permissions extension - fix_permissions, restrict_channels, lock_server, fix_* commands."""

import discord
from discord import app_commands

from ..bot import tree
from ..config import TEST_GUILD_ID


@tree.command(
    name="fix_permissions",
    description="Fix permissions for all roles and channels",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def fix_permissions(interaction: discord.Interaction):
    """Fix role and channel permissions."""
    await interaction.response.defer(ephemeral=True)

    try:
        guild = interaction.guild
        results = []

        everyone_role = guild.default_role
        admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(guild.roles, name="🔧 Maintainer")
        bot_role = discord.utils.get(guild.roles, name="🤖 Bot")
        approved_role = discord.utils.get(guild.roles, name="🎟️ Approved")

        expected_permissions = {
            "🛡️ Admin": discord.Permissions(administrator=True),
            "👀 Observer": discord.Permissions(
                view_channel=True, read_messages=True, read_message_history=True
            ),
            "🔧 Maintainer": discord.Permissions(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                kick_members=True,
                manage_channels=True,
                create_public_threads=True,
                create_private_threads=True,
                manage_threads=True,
                moderate_members=True,
            ),
            "🤖 Bot": discord.Permissions(
                view_channel=True,
                send_messages=True,
                send_messages_in_threads=True,
                create_public_threads=True,
                create_private_threads=True,
                manage_threads=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
                mention_everyone=True,
                use_external_emojis=True,
                add_reactions=True,
                manage_roles=True,
                manage_channels=True,
                manage_messages=True,
                moderate_members=True,
            ),
            "🎮 Gamer": discord.Permissions(read_messages=True),
            "🎟️ Approved": discord.Permissions(read_messages=True),
            "⏳ Pending": discord.Permissions(read_messages=True),
            "❌ Denied": discord.Permissions(read_messages=True),
        }

        for role_name, expected_perms in expected_permissions.items():
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                results.append(f"❌ Role not found: {role_name}")
                continue

            if role.permissions != expected_perms:
                try:
                    await role.edit(permissions=expected_perms)
                    results.append(f"✅ Fixed permissions for role: {role_name}")
                except discord.Forbidden:
                    results.append(
                        f"❌ Cannot edit permissions for role: {role_name} (Forbidden)"
                    )
                except Exception as e:
                    results.append(f"❌ Error fixing role {role_name}: {str(e)}")
            else:
                results.append(f"✓ Role permissions are correct: {role_name}")

        try:
            await everyone_role.edit(
                permissions=discord.Permissions(
                    view_channel=False,
                    connect=True,
                    speak=False,
                    use_application_commands=True,
                    use_embedded_activities=True,
                )
            )
            results.append("✅ Set @everyone to hide all channels by default")
        except Exception as e:
            results.append(f"❌ Failed to reset @everyone permissions: {str(e)}")

        for category in guild.categories:
            try:
                overwrites = {
                    everyone_role: discord.PermissionOverwrite(
                        view_channel=False, read_messages=False
                    )
                }

                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(
                        view_channel=True, read_messages=True, send_messages=True
                    )

                if maintainer_role:
                    overwrites[maintainer_role] = discord.PermissionOverwrite(
                        view_channel=True, read_messages=True, send_messages=True
                    )

                if bot_role:
                    overwrites[bot_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True,
                    )

                is_admin_category = (
                    "admin" in category.name.lower()
                    or "alert" in category.name.lower()
                    or "bot command" in category.name.lower()
                )

                if (
                    approved_role
                    and not is_admin_category
                    and "onboarding" not in category.name.lower()
                ):
                    overwrites[approved_role] = discord.PermissionOverwrite(
                        view_channel=True, read_messages=True, send_messages=True
                    )

                await category.edit(overwrites=overwrites)
                results.append(
                    f"✅ Set default permissions for category: {category.name}"
                )

                for channel in category.channels:
                    if (
                        channel.name == "📖｜start-here"
                        or channel.name == "📬｜get-invite"
                        or channel.name == "🎫｜access-requests"
                        or channel.name.startswith("🔒")
                    ):
                        continue

                    try:
                        await channel.edit(sync_permissions=True)
                        results.append(f"✅ Synced permissions for: {channel.name}")
                    except Exception as e:
                        results.append(f"❌ Failed to sync {channel.name}: {str(e)}")
            except Exception as e:
                results.append(f"❌ Error setting category {category.name}: {str(e)}")

        special_channels = {
            "📖｜start-here": {
                "default": discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=False,
                ),
                "🤖 Bot": discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True,
                ),
            },
            "📬｜get-invite": {
                "default": discord.PermissionOverwrite(
                    view_channel=False, read_messages=False
                ),
                "🎟️ Approved": discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=False,
                ),
                "🤖 Bot": discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True,
                ),
            },
            "🎫｜access-requests": {
                "default": discord.PermissionOverwrite(
                    view_channel=False, read_messages=False
                ),
                "🛡️ Admin": discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True,
                ),
                "🔧 Maintainer": discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True,
                ),
                "🤖 Bot": discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True,
                ),
            },
        }

        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue

            if "admin" in channel.name.lower() or channel.name.startswith("🔒"):
                special_channels[channel.name] = {
                    "default": discord.PermissionOverwrite(
                        view_channel=False, read_messages=False
                    ),
                    "🛡️ Admin": discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        read_message_history=True,
                        send_messages=True,
                    ),
                    "🔧 Maintainer": discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        read_message_history=True,
                        send_messages=True,
                    ),
                    "🤖 Bot": discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        read_message_history=True,
                        send_messages=True,
                    ),
                }

        for channel_name, perms in special_channels.items():
            channel = discord.utils.get(guild.channels, name=channel_name)
            if not channel:
                for guild_channel in guild.channels:
                    if channel_name in guild_channel.name:
                        channel = guild_channel
                        break

            if not channel:
                results.append(f"❌ Channel not found: {channel_name}")
                continue

            for role_name, overwrite in perms.items():
                if role_name == "default":
                    try:
                        await channel.set_permissions(
                            everyone_role, overwrite=overwrite
                        )
                        results.append(
                            f"✅ Set default permissions for channel: {channel.name}"
                        )
                    except Exception as e:
                        results.append(
                            f"❌ Error setting default permissions for channel {channel.name}: {str(e)}"
                        )
                else:
                    role = discord.utils.get(guild.roles, name=role_name)
                    if not role:
                        results.append(
                            f"❌ Role not found for channel permission: {role_name}"
                        )
                        continue

                    try:
                        await channel.set_permissions(role, overwrite=overwrite)
                        results.append(
                            f"✅ Set {role_name} permissions for channel: {channel.name}"
                        )
                    except Exception as e:
                        results.append(
                            f"❌ Error setting {role_name} permissions for channel {channel.name}: {str(e)}"
                        )

        request_channels = [
            ch for ch in guild.channels if ch.name.startswith("request-")
        ]
        for channel in request_channels:
            try:
                channel_parts = channel.name.split("-")
                if len(channel_parts) >= 3:
                    username = "-".join(channel_parts[2:])

                    target_user = None
                    for member in guild.members:
                        if (
                            member.name.lower() == username.lower()
                            or username.lower() in member.name.lower()
                        ):
                            target_user = member
                            break

                    if target_user:
                        await channel.set_permissions(
                            target_user,
                            view_channel=True,
                            read_messages=True,
                            read_message_history=True,
                            send_messages=True,
                        )
                        results.append(
                            f"✅ Fixed permissions for {channel.name} - {target_user.name} can now read history"
                        )
                    else:
                        results.append(
                            f"❌ Could not find user for channel: {channel.name}"
                        )
            except Exception as e:
                results.append(f"❌ Error fixing {channel.name}: {str(e)}")

        embed = discord.Embed(
            title="🔧 Permission Check Results",
            description="Here's what was fixed:",
            color=0x00B8FF,
        )

        chunks = [results[i : i + 10] for i in range(0, len(results), 10)]
        for i, chunk in enumerate(chunks):
            embed.add_field(
                name=f"Results {i+1}/{len(chunks)}",
                value="\n".join(chunk),
                inline=False,
            )

        embed.add_field(
            name="Summary",
            value=(
                "✅ Permission structure:\n"
                "• New users can only see the start-here channel\n"
                "• Start-here history is visible to everyone\n"
                "• All request channels allow users to see their history\n"
                "• Admin channels are restricted to admins and maintainers\n"
                "• Approved users can't access admin areas\n"
                "• Approved users can access media channels"
            ),
            inline=False,
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error updating permissions: {str(e)}", ephemeral=True
        )


@tree.command(
    name="restrict_channels",
    description="Strictly restrict channel visibility for new users",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def restrict_channels(interaction: discord.Interaction):
    """Apply strict channel restrictions."""
    await interaction.response.defer(ephemeral=True)

    try:
        guild = interaction.guild
        results = []

        admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(guild.roles, name="🔧 Maintainer")
        bot_role = discord.utils.get(guild.roles, name="🤖 Bot")
        approved_role = discord.utils.get(guild.roles, name="🎟️ Approved")

        everyone_role = guild.default_role
        try:
            base_perms = discord.Permissions(
                view_channel=False,
                connect=False,
                use_application_commands=True,
                use_embedded_activities=True,
                create_instant_invite=False,
            )
            await everyone_role.edit(permissions=base_perms)
            results.append("✅ Reset @everyone role to minimal permissions")
        except Exception as e:
            results.append(f"❌ Failed to reset @everyone permissions: {str(e)}")

        start_here = discord.utils.get(guild.channels, name="📖｜start-here")

        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue

            try:
                if channel == start_here:
                    overwrites = {
                        everyone_role: discord.PermissionOverwrite(
                            view_channel=True, read_messages=True, send_messages=False
                        )
                    }
                    results.append(f"✅ Set start-here channel visible to everyone")
                elif channel.name == "📬｜get-invite":
                    overwrites = {
                        everyone_role: discord.PermissionOverwrite(
                            view_channel=False, read_messages=False
                        )
                    }
                    if approved_role:
                        overwrites[approved_role] = discord.PermissionOverwrite(
                            view_channel=True, read_messages=True, send_messages=False
                        )
                    results.append(f"✅ Set get-invite channel for approved users only")
                elif channel.name.startswith("🔒") or channel.name.startswith("🎫"):
                    overwrites = {
                        everyone_role: discord.PermissionOverwrite(
                            view_channel=False, read_messages=False
                        )
                    }
                    results.append(f"✅ Set {channel.name} to admin/maintainer only")
                else:
                    overwrites = {
                        everyone_role: discord.PermissionOverwrite(
                            view_channel=False, read_messages=False
                        )
                    }
                    if approved_role:
                        overwrites[approved_role] = discord.PermissionOverwrite(
                            view_channel=True, read_messages=True
                        )
                    results.append(f"✅ Set {channel.name} to approved users only")

                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True,
                    )

                if maintainer_role:
                    overwrites[maintainer_role] = discord.PermissionOverwrite(
                        view_channel=True, read_messages=True, send_messages=True
                    )

                if bot_role:
                    overwrites[bot_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True,
                        embed_links=True,
                        attach_files=True,
                    )

                await channel.edit(overwrites=overwrites)

            except Exception as e:
                results.append(
                    f"❌ Error setting permissions for {channel.name}: {str(e)}"
                )

        embed = discord.Embed(
            title="🔒 Channel Restriction Results",
            description="**STRICT PERMISSIONS APPLIED**",
            color=0xFF0000,
        )

        chunks = [results[i : i + 15] for i in range(0, len(results), 15)]
        for i, chunk in enumerate(chunks):
            embed.add_field(
                name=f"Results {i+1}/{len(chunks)}",
                value="\n".join(chunk),
                inline=False,
            )

        embed.add_field(
            name="⚠️ IMPORTANT",
            value=(
                "**These changes are strict and may restrict access more than expected:**\n"
                "• New users can ONLY see the start-here channel\n"
                "• ALL other channels are hidden until approved\n"
                "• @everyone permissions have been reset to minimal\n"
                "• Channel-specific permissions override category permissions\n\n"
                "If any channel is still visible to unapproved users, please report it."
            ),
            inline=False,
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error restricting channels: {str(e)}", ephemeral=True
        )


@tree.command(
    name="lock_server",
    description="EMERGENCY: Lock down all channels for new users",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def lock_server(interaction: discord.Interaction):
    """Emergency server lockdown."""
    await interaction.response.defer(ephemeral=True)

    try:
        guild = interaction.guild
        results = []
        fixed_channels = 0

        everyone_role = guild.default_role
        admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(guild.roles, name="🔧 Maintainer")
        bot_role = discord.utils.get(guild.roles, name="🤖 Bot")
        approved_role = discord.utils.get(guild.roles, name="🎟️ Approved")

        try:
            minimal_perms = discord.Permissions(
                connect=False,
                speak=False,
                send_messages=False,
                read_messages=False,
                view_channel=False,
                use_application_commands=True,
                use_embedded_activities=True,
            )
            await everyone_role.edit(permissions=minimal_perms)
            results.append("✅ Reset @everyone permissions to absolute minimum")
        except Exception as e:
            results.append(f"❌ Failed to reset @everyone: {str(e)}")

        start_here = discord.utils.get(guild.channels, name="📖｜start-here")

        for category in guild.categories:
            try:
                overwrites = {
                    everyone_role: discord.PermissionOverwrite(
                        view_channel=False,
                        read_messages=False,
                        send_messages=False,
                        read_message_history=False,
                        connect=False,
                        speak=False,
                    )
                }

                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True,
                    )

                if maintainer_role:
                    overwrites[maintainer_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True,
                    )

                if bot_role:
                    overwrites[bot_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True,
                    )

                if approved_role and category.name != "👋 Onboarding":
                    overwrites[approved_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True,
                    )

                await category.edit(overwrites=overwrites)
                results.append(
                    f"✅ Set strict permissions for category: {category.name}"
                )

                for channel in category.channels:
                    try:
                        if channel == start_here:
                            continue

                        if (
                            channel.name.startswith("🔒")
                            or channel.name.startswith("🎫")
                            or channel.name == "📬｜get-invite"
                            or "admin" in channel.name
                        ):
                            special_overwrites = {
                                everyone_role: discord.PermissionOverwrite(
                                    view_channel=False,
                                    read_messages=False,
                                    send_messages=False,
                                )
                            }

                            if admin_role:
                                special_overwrites[admin_role] = (
                                    discord.PermissionOverwrite(
                                        view_channel=True,
                                        read_messages=True,
                                        send_messages=True,
                                    )
                                )

                            if maintainer_role:
                                special_overwrites[maintainer_role] = (
                                    discord.PermissionOverwrite(
                                        view_channel=True,
                                        read_messages=True,
                                        send_messages=True,
                                    )
                                )

                            if bot_role:
                                special_overwrites[bot_role] = (
                                    discord.PermissionOverwrite(
                                        view_channel=True,
                                        read_messages=True,
                                        send_messages=True,
                                    )
                                )

                            if channel.name == "📬｜get-invite" and approved_role:
                                special_overwrites[approved_role] = (
                                    discord.PermissionOverwrite(
                                        view_channel=True,
                                        read_messages=True,
                                        send_messages=False,
                                    )
                                )

                            await channel.edit(
                                overwrites=special_overwrites, sync_permissions=False
                            )
                            results.append(
                                f"✅ Set restricted permissions for {channel.name}"
                            )
                        else:
                            await channel.edit(sync_permissions=True)
                            results.append(
                                f"✅ Synced {channel.name} with category permissions"
                            )

                        fixed_channels += 1
                    except Exception as e:
                        results.append(f"❌ Failed to set {channel.name}: {str(e)}")

            except Exception as e:
                results.append(f"❌ Failed to set category {category.name}: {str(e)}")

        if start_here:
            try:
                start_here_overwrites = {
                    everyone_role: discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=False,
                        read_message_history=True,
                    ),
                }
                if bot_role:
                    start_here_overwrites[bot_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True,
                        embed_links=True,
                        attach_files=True,
                    )

                if admin_role:
                    start_here_overwrites[admin_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True,
                    )

                if maintainer_role:
                    start_here_overwrites[maintainer_role] = (
                        discord.PermissionOverwrite(
                            view_channel=True,
                            read_messages=True,
                            send_messages=True,
                            read_message_history=True,
                        )
                    )

                await start_here.edit(
                    overwrites=start_here_overwrites, sync_permissions=False
                )
                results.append(f"✅ Set start-here visible to everyone but read-only")
                fixed_channels += 1
            except Exception as e:
                results.append(f"❌ Failed to set start-here channel: {str(e)}")

        embed = discord.Embed(
            title="🚨 EMERGENCY SERVER LOCKDOWN",
            description="**The server has been locked down with strict permissions:**",
            color=0xFF0000,
        )

        embed.add_field(
            name="📊 Stats",
            value=f"• Fixed {fixed_channels} channels\n• Reset @everyone permissions\n• Applied explicit denies everywhere",
            inline=False,
        )

        chunks = [results[i : i + 10] for i in range(0, len(results), 10)]
        for i, chunk in enumerate(chunks[:3]):
            embed.add_field(
                name=f"Results {i+1}/{min(len(chunks), 3)}",
                value="\n".join(chunk),
                inline=False,
            )

        embed.add_field(
            name="🔐 Security Configuration",
            value=(
                "**STRICT ACCESS CONTROL ENABLED:**\n"
                "• New users can ONLY see start-here channel\n"
                "• All other channels are completely hidden\n"
                "• Category permissions reset with explicit denies\n"
                "• Channel-specific permissions applied\n"
                "• @everyone role has been locked down"
            ),
            inline=False,
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(
            f"❌ Emergency lockdown failed: {str(e)}", ephemeral=True
        )


@tree.command(
    name="fix_start_here",
    description="Fix start-here channel permissions",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def fix_start_here(interaction: discord.Interaction):
    """Fix start-here channel permissions."""
    await interaction.response.defer(ephemeral=True)

    try:
        guild = interaction.guild
        everyone_role = guild.default_role
        bot_role = discord.utils.get(guild.roles, name="🤖 Bot")

        start_here = discord.utils.get(guild.channels, name="📖｜start-here")
        if not start_here:
            for channel in guild.channels:
                if "start-here" in channel.name:
                    start_here = channel
                    break

        if not start_here:
            await interaction.followup.send(
                "❌ Could not find the start-here channel!", ephemeral=True
            )
            return

        await start_here.set_permissions(
            everyone_role,
            view_channel=True,
            read_messages=True,
            read_message_history=True,
            send_messages=False,
        )

        if bot_role:
            await start_here.set_permissions(
                bot_role,
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
            )

        await interaction.followup.send(
            "✅ Fixed start-here channel! Everyone can now view messages but not send them.",
            ephemeral=True,
        )

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(
    name="fix_read_permissions",
    description="Fix read history permissions for important channels",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def fix_read_permissions(interaction: discord.Interaction):
    """Fix read permissions for start-here and request channels."""
    await interaction.response.defer(ephemeral=True)

    try:
        guild = interaction.guild
        everyone_role = guild.default_role
        results = []

        start_here = discord.utils.get(guild.channels, name="📖｜start-here")
        if start_here:
            await start_here.set_permissions(
                everyone_role,
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=False,
            )
            results.append(
                "✅ Fixed start-here channel - everyone can now read message history"
            )
        else:
            results.append("❌ Could not find start-here channel")

        request_channels = [
            channel for channel in guild.channels if channel.name.startswith("request-")
        ]
        for channel in request_channels:
            try:
                channel_parts = channel.name.split("-")
                if len(channel_parts) >= 3:
                    username = "-".join(channel_parts[2:])

                    target_user = None
                    for member in guild.members:
                        if (
                            member.name.lower() == username.lower()
                            or username.lower() in member.name.lower()
                        ):
                            target_user = member
                            break

                    if target_user:
                        await channel.set_permissions(
                            target_user,
                            view_channel=True,
                            read_messages=True,
                            read_message_history=True,
                            send_messages=True,
                        )
                        results.append(
                            f"✅ Fixed permissions for {channel.name} - {target_user.name} can now read history"
                        )
                    else:
                        results.append(
                            f"❌ Could not find user for channel: {channel.name}"
                        )
            except Exception as e:
                results.append(f"❌ Error fixing {channel.name}: {str(e)}")

        embed = discord.Embed(
            title="🔧 Read Permission Fix",
            description="Results of fixing read permissions:",
            color=0x00B8FF,
        )

        embed.add_field(name="Changes", value="\n".join(results), inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

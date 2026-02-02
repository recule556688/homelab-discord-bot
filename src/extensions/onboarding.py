"""Onboarding extension - access requests, embeds, and views."""

import discord
from discord import app_commands
from discord.ui import Button, View

from ..bot import tree
from ..config import TEST_GUILD_ID
from ..utils import load_request_counter, save_request_counter


class OnboardingView(View):
    """View with Request Access button for start-here channel."""

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            Button(
                label="🎟 Request Access",
                style=discord.ButtonStyle.primary,
                custom_id="request_access",
            )
        )


class ChannelManagementView(View):
    """View with Delete Channel button for admin/moderator use."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🗑️ Delete Channel",
        style=discord.ButtonStyle.secondary,
        custom_id="delete_channel",
    )
    async def delete_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        has_permission = False
        admin_role = discord.utils.get(interaction.guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(
            interaction.guild.roles, name="🔧 Maintainer"
        )

        if (admin_role and admin_role in interaction.user.roles) or (
            maintainer_role and maintainer_role in interaction.user.roles
        ):
            has_permission = True

        if not has_permission:
            await interaction.response.send_message(
                "❌ 🇺🇸 You don't have permission to delete this channel. Only Admins and Maintainers can do this.\n\n"
                + "🇫🇷 Vous n'avez pas la permission de supprimer ce canal. Seuls les Admins et les Mainteneurs peuvent le faire.",
                ephemeral=True,
            )
            return

        try:
            await interaction.response.defer(ephemeral=True)
            channel = interaction.channel
            await channel.delete()
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error deleting channel: {str(e)}", ephemeral=True
            )


class DenialReasonModal(discord.ui.Modal):
    """Modal for collecting denial reason when denying access request."""

    def __init__(self, view_instance):
        super().__init__(title="Denial Reason")
        self.view_instance = view_instance

        self.reason_input = discord.ui.TextInput(
            label="Reason for denial",
            placeholder="Please explain why this request is being denied...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.view_instance.process_denial(interaction, self.reason_input.value)


class AccessRequestView(View):
    """View with Approve/Deny buttons for access request channels."""

    def __init__(self, user_id: int, channel_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.channel_id = channel_id

    @discord.ui.button(
        label="✅ Approve",
        style=discord.ButtonStyle.success,
        custom_id="approve_request",
    )
    async def approve_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        has_permission = False
        admin_role = discord.utils.get(interaction.guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(
            interaction.guild.roles, name="🔧 Maintainer"
        )

        if (admin_role and admin_role in interaction.user.roles) or (
            maintainer_role and maintainer_role in interaction.user.roles
        ):
            has_permission = True

        if not has_permission:
            try:
                await interaction.response.send_message(
                    "❌ 🇺🇸 You don't have permission to approve requests. Only Admins and Maintainers can do this.\n\n"
                    + "🇫🇷 Vous n'avez pas la permission d'approuver les demandes. Seuls les Admins et les Mainteneurs peuvent le faire.",
                    ephemeral=True,
                )
            except discord.errors.NotFound:
                return
            return

        try:
            channel = interaction.channel
            request_number = "Unknown"
            try:
                channel_name_parts = channel.name.split("-")
                if len(channel_name_parts) >= 2:
                    request_number = channel_name_parts[1]
            except Exception:
                pass

            try:
                await interaction.response.defer()
            except discord.errors.NotFound:
                return

            try:
                user = await interaction.guild.fetch_member(self.user_id)
                if not user:
                    await interaction.followup.send(
                        "❌ Error: Could not find the user who requested access.",
                        ephemeral=True,
                    )
                    return

                pending_role = discord.utils.get(
                    interaction.guild.roles, name="⏳ Pending"
                )
                if pending_role and pending_role in user.roles:
                    await user.remove_roles(pending_role)

                denied_role = discord.utils.get(
                    interaction.guild.roles, name="❌ Denied"
                )
                if denied_role and denied_role in user.roles:
                    await user.remove_roles(denied_role)

                approved_role = discord.utils.get(
                    interaction.guild.roles, name="🎟️ Approved"
                )
                if approved_role:
                    await user.add_roles(approved_role)

                    embed = discord.Embed(
                        title=f"✅ Request #{request_number} Approved | Demande #{request_number} Approuvée",
                        description=f"🇺🇸 {user.mention} has been approved for access!\n\n"
                        + f"They can now access the invite channel.\n\n"
                        + f"🇫🇷 {user.mention} a été approuvé pour l'accès !\n\n"
                        + f"Ils peuvent maintenant accéder au canal d'invitation.",
                        color=0x00FF00,
                    )
                    await interaction.followup.send(embed=embed)

                    try:
                        dm_embed = discord.Embed(
                            title=f"🎉 Access Request #{request_number} Approved! | Demande d'Accès #{request_number} Approuvée !",
                            description="🇺🇸 Your access request has been approved! You can now access the invite channel.\n\n"
                            + "🇫🇷 Votre demande d'accès a été approuvée ! Vous pouvez maintenant accéder au canal d'invitation.",
                            color=0x00FF00,
                        )
                        await user.send(embed=dm_embed)
                    except Exception:
                        await channel.send(
                            "Note: Could not send DM to user (they may have DMs disabled)"
                        )

                    await channel.send(
                        f"✅ 🇺🇸 Request #{request_number} process complete. An admin or maintainer can delete this channel using the button at the top.\n\n"
                        + f"🇫🇷 Traitement de la demande #{request_number} terminé. Un admin ou un mainteneur peut supprimer ce canal en utilisant le bouton en haut.",
                        delete_after=300,
                    )
                else:
                    await interaction.followup.send(
                        "❌ Error: Could not find the Approved role.", ephemeral=True
                    )
            except discord.NotFound:
                await interaction.followup.send(
                    "❌ Error: Could not find the user who requested access.",
                    ephemeral=True,
                )
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Error while approving: {str(e)}", ephemeral=True
                )

        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Error: {str(e)}", ephemeral=True
                )
            else:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @discord.ui.button(
        label="❌ Deny", style=discord.ButtonStyle.danger, custom_id="deny_request"
    )
    async def deny_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        has_permission = False
        admin_role = discord.utils.get(interaction.guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(
            interaction.guild.roles, name="🔧 Maintainer"
        )

        if (admin_role and admin_role in interaction.user.roles) or (
            maintainer_role and maintainer_role in interaction.user.roles
        ):
            has_permission = True

        if not has_permission:
            await interaction.response.send_message(
                "❌ 🇺🇸 You don't have permission to deny requests. Only Admins and Maintainers can do this.\n\n"
                + "🇫🇷 Vous n'avez pas la permission de refuser les demandes. Seuls les Admins et les Mainteneurs peuvent le faire.",
                ephemeral=True,
            )
            return

        modal = DenialReasonModal(self)
        await interaction.response.send_modal(modal)

    async def process_denial(self, interaction: discord.Interaction, reason: str):
        try:
            channel = interaction.channel
            request_number = "Unknown"
            try:
                channel_name_parts = channel.name.split("-")
                if len(channel_name_parts) >= 2:
                    request_number = channel_name_parts[1]
            except Exception:
                pass

            try:
                user = await interaction.guild.fetch_member(self.user_id)
                if not user:
                    await interaction.followup.send(
                        "❌ Error: Could not find the user who requested access.",
                        ephemeral=True,
                    )
                    return

                pending_role = discord.utils.get(
                    interaction.guild.roles, name="⏳ Pending"
                )
                if pending_role and pending_role in user.roles:
                    await user.remove_roles(pending_role)

                approved_role = discord.utils.get(
                    interaction.guild.roles, name="🎟️ Approved"
                )
                if approved_role and approved_role in user.roles:
                    await user.remove_roles(approved_role)

                denied_role = discord.utils.get(
                    interaction.guild.roles, name="❌ Denied"
                )
                if denied_role:
                    await user.add_roles(denied_role)

                formatted_reason = f"**Reason | Raison:**\n{reason}"

                embed = discord.Embed(
                    title=f"❌ Request #{request_number} Denied | Demande #{request_number} Refusée",
                    description=f"🇺🇸 {user.mention}'s access request has been denied.\n\n"
                    + f"🇫🇷 La demande d'accès de {user.mention} a été refusée.",
                    color=0xFF0000,
                )
                embed.add_field(
                    name="Denial Reason | Raison du refus",
                    value=formatted_reason,
                    inline=False,
                )

                await interaction.followup.send(embed=embed)

                try:
                    dm_embed = discord.Embed(
                        title=f"❌ Access Request #{request_number} Denied | Demande d'Accès #{request_number} Refusée",
                        description="🇺🇸 Your access request has been denied.\n\n"
                        + "🇫🇷 Votre demande d'accès a été refusée.",
                        color=0xFF0000,
                    )
                    dm_embed.add_field(
                        name="Denial Reason | Raison du refus",
                        value=formatted_reason,
                        inline=False,
                    )
                    dm_embed.add_field(
                        name="Questions? | Des questions?",
                        value="🇺🇸 If you have questions, please contact a moderator.\n\n"
                        + "🇫🇷 Si vous avez des questions, veuillez contacter un modérateur.",
                        inline=False,
                    )

                    await user.send(embed=dm_embed)
                except Exception:
                    await channel.send(
                        "Note: Could not send DM to user (they may have DMs disabled)"
                    )

                await channel.send(
                    f"✅ 🇺🇸 Request #{request_number} process complete. An admin or maintainer can delete this channel using the button at the top.\n\n"
                    + f"🇫🇷 Traitement de la demande #{request_number} terminé. Un admin ou un mainteneur peut supprimer ce canal en utilisant le bouton en haut.",
                    delete_after=300,
                )
            except discord.NotFound:
                await interaction.followup.send(
                    "❌ Error: Could not find the user who requested access.",
                    ephemeral=True,
                )
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Error while denying: {str(e)}", ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


class ThreadManagementView(View):
    """View with Delete Thread button for admin/moderator use."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🗑️ Delete Thread",
        style=discord.ButtonStyle.secondary,
        custom_id="delete_thread",
    )
    async def delete_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        has_permission = False
        admin_role = discord.utils.get(interaction.guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(
            interaction.guild.roles, name="🔧 Maintainer"
        )

        if (admin_role and admin_role in interaction.user.roles) or (
            maintainer_role and maintainer_role in interaction.user.roles
        ):
            has_permission = True

        if not has_permission:
            await interaction.response.send_message(
                "❌ 🇺🇸 You don't have permission to delete this thread. Only Admins and Maintainers can do this.\n\n"
                + "🇫🇷 Vous n'avez pas la permission de supprimer ce fil. Seuls les Admins et les Mainteneurs peuvent le faire.",
                ephemeral=True,
            )
            return

        try:
            await interaction.response.defer(ephemeral=True)
            thread = interaction.channel
            await thread.delete()
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error deleting thread: {str(e)}", ephemeral=True
            )


def create_onboarding_embed():
    """Create the onboarding/welcome embed."""
    embed = discord.Embed(
        title="🎬 Welcome to Our Media Server!", description="", color=0x00B8FF
    )

    embed.add_field(
        name="🇺🇸 English",
        value=(
            "**How to Get Started:**\n"
            "1. Click the 'Request Access' button below\n"
            "2. Wait for moderator approval\n"
            "3. Once approved, you'll receive a Plex invite via Wizarr\n"
            "4. Use Overseerr to request new content\n"
            "5. Enjoy your media on Plex!\n\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="🇫🇷 Français",
        value=(
            "**Comment commencer:**\n"
            "1. Cliquez sur le bouton 'Demander l'accès' ci-dessous\n"
            "2. Attendez l'approbation d'un modérateur\n"
            "3. Une fois approuvé, vous recevrez une invitation Plex via Wizarr\n"
            "4. Utilisez Overseerr pour demander du nouveau contenu\n"
            "5. Profitez de vos médias sur Plex!\n\n"
        ),
        inline=False,
    )

    return embed


def create_invite_embed():
    """Create the get-invite embed."""
    embed = discord.Embed(
        title="🎟️ Get Your Media Server Invite",
        description=(
            "Welcome to the invite channel! Here's your direct invite link:\n\n"
            "Follow the steps below to get started with our media server."
        ),
        color=0x00B8FF,
    )

    embed.add_field(
        name="🇺🇸 Getting Started",
        value=(
            "**Step 1: Get Your Plex Invite**\n"
            "• Click the invite link below\n"
            "**🔗 [Click Here to Join](https://wizarr.tessdev.fr/j/QOZEPF)**\n\n"
            "• Sign up with your email\n"
            "• Accept the Plex invitation\n\n"
            "**Step 2: Access Content**\n"
            "• Download [Plex application](https://www.plex.tv/downloads) application on your PC, Mac, or mobile device\n"
            "• Or use the web app at [Plex Web App](https://plex.tessdev.fr)\n"
            "• Sign in with your account\n"
            "• Start streaming!\n\n"
            "**Step 3: Request Content**\n"
            "• Use [Overseerr](https://overseer.tessdev.fr) to request movies and shows\n"
            "• Track your requests status\n"
            "• Get notified when content is available"
        ),
        inline=False,
    )

    embed.add_field(
        name="🇫🇷 Pour Commencer",
        value=(
            "**Étape 1: Obtenir Votre Invitation Plex**\n"
            "• Cliquez sur le lien d'invitation ci-dessous\n"
            "**🔗 [Cliquez Ici pour Joindre](https://wizarr.tessdev.fr/j/QOZEPF)**\n\n"
            "• Inscrivez-vous avec votre email\n"
            "• Acceptez l'invitation Plex\n\n"
            "**Étape 2: Accéder au Contenu**\n"
            "• Téléchargez [L'application Plex](https://www.plex.tv/downloads) sur votre PC, Mac, ou appareil mobile\n"
            "• Ou utilisez l'application web à [Plex Web App](https://plex.tessdev.fr)\n"
            "• Connectez-vous avec votre compte\n"
            "• Commencez à streamer!\n\n"
            "**Étape 3: Demander du Contenu**\n"
            "• Utilisez [Overseerr](https://overseer.tessdev.fr) pour demander des films et séries\n"
            "• Suivez le statut de vos demandes\n"
            "• Soyez notifié quand le contenu est disponible"
        ),
        inline=False,
    )

    embed.add_field(
        name="ℹ️ Important Notes | Notes Importantes\n",
        value=(
            "\n**🇺🇸**\n"
            "• This invite link is for approved members only\n"
            "• Keep your login information secure\n"
            "• Don't share your account with others\n"
            "• For support, contact an admin\n\n"
            "**🇫🇷**\n"
            "• Ce lien d'invitation est réservé aux membres approuvés\n"
            "• Gardez vos informations de connexion sécurisées\n"
            "• Ne partagez pas votre compte\n"
            "• Pour le support, contactez un admin"
        ),
        inline=False,
    )

    embed.set_footer(
        text="🔐 Access is limited to approved members only | Accès limité aux membres approuvés",
        icon_url="https://cdn.discordapp.com/emojis/1039485258276737024.webp?size=96&quality=lossless",
    )

    return embed


async def handle_access_request(interaction: discord.Interaction):
    """Handle the Request Access button click."""
    await interaction.response.defer(ephemeral=True)

    try:
        guild = interaction.guild
        user = interaction.user

        request_counter = load_request_counter() + 1
        save_request_counter(request_counter)

        admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(guild.roles, name="🔧 Maintainer")
        bot_role = discord.utils.get(guild.roles, name="🤖 Bot")
        pending_role = discord.utils.get(guild.roles, name="⏳ Pending")

        if pending_role and pending_role not in user.roles:
            try:
                await user.add_roles(pending_role)
            except Exception as e:
                print(f"Error adding Pending role to user: {e}")

        onboarding_category = discord.utils.get(guild.categories, name="👋 Onboarding")
        if not onboarding_category:
            await interaction.followup.send(
                "❌ Error: Could not find the Onboarding category!", ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=False, send_messages=False
            ),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_channels=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
            ),
        }

        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True
            )
        if maintainer_role:
            overwrites[maintainer_role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True
            )
        if bot_role:
            overwrites[bot_role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_channels=True,
                embed_links=True,
                attach_files=True,
            )

        channel_name = (
            f"request-{request_counter:04d}-{user.name.lower().replace(' ', '-')}"
        )
        request_channel = await guild.create_text_channel(
            name=channel_name,
            category=onboarding_category,
            overwrites=overwrites,
            topic=f"Access request #{request_counter} from {user.name} ({user.id})",
        )

        admin_embed = discord.Embed(
            title=f"🔧 Request Management #{request_counter}",
            description=f"This is a private channel for an access request from {user.mention}.\n\n"
            + f"{admin_role.mention if admin_role else 'Admins'} and "
            + f"{maintainer_role.mention if maintainer_role else 'Maintainers'}: "
            + f"You can delete this channel using the button below when finished.",
            color=0x808080,
        )

        admin_embed.add_field(
            name="🇫🇷 Gestion de Requête",
            value=f"Ceci est un canal privé pour une demande d'accès de {user.mention}.\n\n"
            + f"{admin_role.mention if admin_role else 'Admins'} et "
            + f"{maintainer_role.mention if maintainer_role else 'Mainteneurs'}: "
            + f"Vous pouvez supprimer ce canal en utilisant le bouton ci-dessous une fois terminé.",
            inline=False,
        )

        channel_mgmt_view = ChannelManagementView()
        await request_channel.send(embed=admin_embed, view=channel_mgmt_view)

        user_embed = discord.Embed(
            title=f"🎟 Access Request #{request_counter} | Demande d'Accès #{request_counter}",
            description=f"🇺🇸 User: {user.mention}\n🇫🇷 Utilisateur: {user.mention}\n\n"
            + f"🇺🇸 Please explain why you want access to the media server:\n"
            + f"🇫🇷 Veuillez expliquer pourquoi vous souhaitez accéder au serveur multimédia:"
            + f"\n\n🇺🇸 Also specify here if you want access to the game server requesting:\n\n"
            + f"🇫🇷 Veuillez également préciser ici si vous souhaitez accéder au service de création de serveur de jeu:\n",
            color=0x00B8FF,
        )

        if pending_role:
            user_embed.add_field(
                name="Status | Statut",
                value=f"🇺🇸 You've been assigned the {pending_role.mention} role while your request is processed.\n"
                + f"🇫🇷 Le rôle {pending_role.mention} vous a été attribué pendant le traitement de votre demande.",
                inline=False,
            )

        request_view = AccessRequestView(user.id, request_channel.id)
        await request_channel.send(embed=user_embed, view=request_view)

        await interaction.followup.send(
            f"✅ 🇺🇸 Your access request #{request_counter} has been submitted! Please check the private channel: {request_channel.mention}\n\n"
            + f"🇫🇷 Votre demande d'accès #{request_counter} a été soumise ! Veuillez consulter le canal privé: {request_channel.mention}",
            ephemeral=True,
        )

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(
    name="send_intro_embed",
    description="Send the onboarding embed to the start-here channel.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def send_intro_embed(interaction: discord.Interaction):
    """Send onboarding embed to start-here channel."""
    await interaction.response.defer(ephemeral=True)

    try:
        start_here_channel = discord.utils.get(
            interaction.guild.channels, name="📖｜start-here"
        )
        if not start_here_channel:
            await interaction.followup.send(
                "❌ Could not find the start-here channel!", ephemeral=True
            )
            return

        embed = create_onboarding_embed()
        view = OnboardingView()
        await start_here_channel.send(embed=embed, view=view)

        await interaction.followup.send(
            "✅ Onboarding embed sent successfully!", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(
    name="send_invite_embed",
    description="Send the get-invite embed to the channel.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def send_invite_embed(interaction: discord.Interaction):
    """Send invite embed to get-invite channel."""
    await interaction.response.defer(ephemeral=True)

    try:
        invite_channel = discord.utils.get(
            interaction.guild.channels, name="📬｜get-invite"
        )
        if not invite_channel:
            await interaction.followup.send(
                "❌ Could not find the get-invite channel!", ephemeral=True
            )
            return

        embed = create_invite_embed()
        await invite_channel.send(embed=embed)

        await interaction.followup.send(
            "✅ Invite embed sent successfully!", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

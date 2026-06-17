from django.conf import settings
from django.db import models
from django.urls import reverse


class Area(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=-1.286389)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=36.817223)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Building(models.Model):
    caretaker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='buildings')
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name='buildings')
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True, blank=True)
    landmark = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    # Optional fallback URL kept for existing sample/seed data. Real caretakers upload images from device.
    image_url = models.URLField(blank=True)
    image = models.ImageField(upload_to='building_images/', blank=True)
    amenities = models.CharField(max_length=255, blank=True, help_text='Comma separated amenities')
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['area__name', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('building_detail', args=[self.slug])

    @property
    def display_image_url(self):
        if self.image:
            return self.image.url
        return self.image_url

    @property
    def available_units(self):
        return self.units.filter(status=Unit.AVAILABLE)

    @property
    def available_count(self):
        return self.available_units.count()

    @property
    def price_from(self):
        first = self.available_units.order_by('rent').first()
        return first.rent if first else None


class Unit(models.Model):
    AVAILABLE = 'available'
    OCCUPIED = 'occupied'
    RESERVED = 'reserved'
    MAINTENANCE = 'maintenance'
    STATUS_CHOICES = [
        (AVAILABLE, 'Available'),
        (OCCUPIED, 'Occupied'),
        (RESERVED, 'Reserved'),
        (MAINTENANCE, 'Maintenance'),
    ]
    TYPE_CHOICES = [
        ('bedsitter', 'Bedsitter'),
        ('studio', 'Studio'),
        ('one_bedroom', 'One bedroom'),
        ('two_bedroom', 'Two bedroom'),
        ('three_bedroom', 'Three bedroom'),
        ('shop', 'Shop unit'),
    ]

    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='units')
    unit_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    label = models.CharField(max_length=50, blank=True, help_text='Example: A12, Ground floor, Unit 4')
    rent = models.PositiveIntegerField()
    deposit = models.PositiveIntegerField(default=0)
    service_charge = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=AVAILABLE)
    image_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['rent', 'unit_type']

    def __str__(self):
        return f'{self.get_unit_type_display()} at {self.building.name}'

    @property
    def move_in_cost(self):
        return self.rent + self.deposit + self.service_charge

    @property
    def cover_image_url(self):
        if self.image_url:
            return self.image_url
        first_image = self.images.first()
        return first_image.display_url if first_image else ''


class UnitImage(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='images')
    # Caretakers upload local unit photos from device; URL remains only for legacy sample data.
    image = models.ImageField(upload_to='unit_images/', blank=True)
    image_url = models.URLField(blank=True)
    caption = models.CharField(max_length=120, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']

    @property
    def display_url(self):
        if self.image:
            return self.image.url
        return self.image_url

    def __str__(self):
        return self.caption or f'Image for {self.unit}'


class SearchEvent(models.Model):
    query = models.CharField(max_length=180, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    radius_km = models.PositiveIntegerField(default=5)
    result_count = models.PositiveIntegerField(default=0)
    session_key = models.CharField(max_length=80, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.query or f'Search near {self.latitude}, {self.longitude}'


class ViewingRequest(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='viewing_requests')
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class AssistantMessage(models.Model):
    USER = 'user'
    ASSISTANT = 'assistant'
    ROLE_CHOICES = [(USER, 'User'), (ASSISTANT, 'Assistant')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class CachedPlace(models.Model):
    query = models.CharField(max_length=180, unique=True)
    label = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    source = models.CharField(max_length=40, default='nominatim')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['query']

    def __str__(self):
        return self.label


class SavedProperty(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_properties')
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.CASCADE, related_name='saved_by')
    # Legacy fallback kept so old local databases with building-level saves can still migrate safely.
    building = models.ForeignKey(Building, null=True, blank=True, on_delete=models.CASCADE, related_name='legacy_saved_by')
    note = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'unit'], name='unique_saved_unit_per_user'),
        ]

    @property
    def saved_unit(self):
        if self.unit_id:
            return self.unit
        if self.building_id:
            return self.building.available_units.order_by('rent').first()
        return None

    @property
    def saved_building(self):
        if self.unit_id:
            return self.unit.building
        return self.building

    def __str__(self):
        item = self.saved_unit or self.saved_building
        return f'{self.user.username} saved {item}'
